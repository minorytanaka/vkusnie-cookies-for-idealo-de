import logging
from typing import Optional

from python_rucaptcha.re_captcha import ReCaptcha

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("solve_captcha")


def solve_recaptcha_rucaptcha(
    sitekey: str, page_url: str, api_key: str
) -> Optional[str]:
    logger.info(
        f"Начало решения reCAPTCHA через RuCaptcha | sitekey={sitekey} | url={page_url}"
    )
    try:
        result = ReCaptcha(
            rucaptcha_key=api_key,
            websiteURL=page_url,
            websiteKey=sitekey,
        ).captcha_handler()
        logger.debug(f"Ответ от RuCaptcha: {result}")

        if result.get("errorId") == 0 and result.get("status") == "ready":
            solution = result.get("solution") or {}
            token = solution.get("gRecaptchaResponse") or solution.get("token")
            logger.info(
                f"Успешно получен токен reCAPTCHA: {token[:20]}... (длина {len(token)})"
            )
            return token
        else:
            logger.warning(f"RuCaptcha вернул ошибку или не готов: {result}")
    except Exception:
        logger.warning("Ошибка решения reCAPTCHA через RuCaptcha", exc_info=True)
    return None
