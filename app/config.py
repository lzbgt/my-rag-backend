from decouple import config as dcfg

SQLALCHEMY_DATABASE_URL = dcfg("SQLALCHEMY_DATABASE_URL")
PORT = dcfg("PORT", cast=int, default=3000)
WECHAT_APPID = dcfg("WECHAT_APPID")
WECHAT_SECRET = dcfg("WECHAT_SECRET")
WECHAT_LOGIN_URL = dcfg("WECHAT_LOGIN_URL")
LLM_API_SEC = dcfg("LLM_API_SEC")
MY_API_SEC = dcfg("MY_API_SEC")
MY_ACTIVATE_CODE_SEC = dcfg("MY_ACTIVATE_CODE_SEC")
assert SQLALCHEMY_DATABASE_URL and WECHAT_APPID and WECHAT_SECRET and WECHAT_LOGIN_URL and LLM_API_SEC and MY_ACTIVATE_CODE_SEC and MY_API_SEC
