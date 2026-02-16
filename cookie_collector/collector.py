import logging
import random
from typing import Optional
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from solve_captcha import solve_recaptcha_rucaptcha

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler()],
)


async def get_cookies_via_playwright(
    page_url: str,
    proxy_pool: list[str],
    rucaptcha_api_key: str = "",
    headless: bool = False,
    page_timeout: float = 30000,
) -> Optional[tuple[dict[str, str], str, bool]]:  # cookies, proxy, after_captcha
    """
    Возвращает: (cookies_dict, used_proxy, after_captcha)
    """

    logger.info(
        f"Запуск получения куки | URL={page_url} | headless={headless} | timeout={page_timeout}ms | прокси в пуле: {len(proxy_pool)}"
    )

    used_proxy_str = random.choice(proxy_pool)
    logger.info(f"Выбран прокси: {used_proxy_str}")
    proxy = parse_proxy(used_proxy_str)
    async with async_playwright() as p:
        logger.info("Запуск браузера chromium")
        browser = await p.webkit.launch(headless=headless, proxy=proxy)
        try:
            logger.info("Создание нового контекста браузера")
            context = await browser.new_context(
                proxy=proxy, screen={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            logger.info(f"Переход по URL: {page_url}")

            response = await page.goto(
                page_url, wait_until="commit", timeout=page_timeout
            )

            status = response.status if response else 0
            if status != 429:
                logger.info(
                    f"Статус код НЕ 429 ({status}) - пропускаем попытку | URL: {page.url}"
                )
                return None

            logger.info("Обнаружен 429 - это капча, начинаем решение")

            after_captcha = True
            sitekey = None

            try:
                logger.info("Поиск sitekey reCAPTCHA")
                await page.wait_for_selector("[data-sitekey]", timeout=15000)
                el = await page.query_selector("[data-sitekey]")
                if el:
                    sitekey = await el.get_attribute("data-sitekey")
                    logger.info(f"Найден sitekey в основном документе: {sitekey}")
                if not sitekey:
                    logger.info("sitekey не найден в основном, ищем в iframe")
                    frame = page.frame_locator("iframe[src*='recaptcha']").first
                    if frame:
                        el = await frame.locator(".g-recaptcha[data-sitekey]").first
                        if el:
                            sitekey = await el.get_attribute("data-sitekey")
                            logger.info(f"Найден sitekey в iframe: {sitekey}")
            except Exception as e:
                logger.warning(f"Не удалось найти sitekey: {e}")

            if sitekey and rucaptcha_api_key:
                logger.info(f"Начинаем решение капчи | sitekey={sitekey}")
                token = solve_recaptcha_rucaptcha(sitekey, page_url, rucaptcha_api_key)
                if token:
                    logger.info("Токен успешно получен, подставляем в страницу")
                    await page.evaluate(
                        """
                        (token) => {
                            const textarea = document.getElementById('g-recaptcha-response')
                                || document.querySelector('[name="g-recaptcha-response"]');
                            if (textarea) {
                                textarea.innerHTML = token;
                                textarea.value = token;
                            }
                            if (typeof ___grecaptcha_cfg !== 'undefined') {
                                const clients = Object.values(___grecaptcha_cfg.clients || {});
                                for (const c of clients) {
                                    const callbacks = c.callback || [];
                                    if (callbacks.length) callbacks.forEach(f => f(token));
                                }
                            }
                            const cb = window.___recaptchaCallback || window.onRecaptchaSuccess;
                            if (typeof cb === 'function') cb(token);
                        }
                        """,
                        token,
                    )
                    logger.debug("Токен подставлен, ждём 2 секунды")
                    await page.wait_for_timeout(2000)

                    # Cookie consent
                    logger.info("Проверка баннера cookie consent")
                    deny_btn = page.locator(
                        'div.buttons-row button[data-action-type="deny"], button.uc-deny-button, #deny'
                    ).first
                    try:
                        await deny_btn.wait_for(state="visible", timeout=10000)
                        logger.info("Баннер cookie consent найден - кликаем 'Ablehnen'")
                        await deny_btn.click()
                        await page.wait_for_timeout(1000)
                    except Exception:
                        logger.debug("Баннер cookie consent не появился")

                    logger.debug("Поиск кнопки submit")
                    submit_button = await page.query_selector(
                        'input[type="submit"][value="weiter"].button.expanded'
                    )
                    if submit_button:
                        logger.info("Кнопка submit найдена - кликаем")
                        await submit_button.click()
                        try:
                            await page.wait_for_load_state("networkidle", timeout=30000)
                            logger.info("Редирект завершён")
                        except Exception:
                            logger.warning("Ожидание редиректа не сработало")

                        logger.info(f"Текущий URL после submit: {page.url}")
                    else:
                        logger.warning("Кнопка submit не найдена")
                else:
                    logger.warning("Не удалось получить токен от RuCaptcha")
            else:
                logger.warning("Капча нужна, но sitekey или ключ API не найден")

            # Собираем куки
            raw_cookies = await context.cookies()
            logger.info(f"Получено сырых куки: {len(raw_cookies)} шт")

            if len(raw_cookies) <= 11:
                logger.warning(f"Мало куки ({len(raw_cookies)} < 10) - ретрай")
                return None

            cookies_dict = {c["name"]: c["value"] for c in raw_cookies}
            logger.info(
                f"Успешно получено {len(cookies_dict)} куки | "
                f"after_captcha={after_captcha} | proxy={used_proxy_str}"
            )
            return cookies_dict, used_proxy_str, after_captcha
        except Exception:
            logger.error("Ошибка Playwright", exc_info=True)
        finally:
            logger.debug("Закрытие браузера")
            await browser.close()
    return None


def parse_proxy(proxy_str: str) -> dict:
    """Парсит строку прокси в формат для Playwright."""

    parsed = urlparse(proxy_str)
    if not parsed.scheme:
        parsed = urlparse(f"http://{proxy_str}")
    server = f"{parsed.scheme}://{parsed.hostname}:{parsed.port or 80}"
    result = {"server": server}
    if parsed.username and parsed.password:
        result.update({"username": parsed.username, "password": parsed.password})
    return result
