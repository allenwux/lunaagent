import base64
import jwt
import os, requests, datetime, json
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from Agent.Exception.LunaExceptions import LunaUserException, LunaServerException
from Agent.Data.AgentUser import AgentUser
from http import HTTPStatus

class InvalidAuthorizationToken(Exception):
    def __init__(self, details):
        super().__init__('Invalid authorization token: ' + details)

OPENID_CONFIGURATION_URL = "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration"

JWT_PUBLIC_KEY_LAST_UPDATED_TIME_ENV_NAME = "JWT_PUBLIC_KEY_LAST_UPDATED_TIME"
JWT_PUBLIC_KEYS_ENV_NAME = "JWT_PUBLIC_KEYS"


class AuthenticationHelper(object):
    
    @staticmethod
    def get_keys():
        last_updated_time = None
        if JWT_PUBLIC_KEY_LAST_UPDATED_TIME_ENV_NAME in os.environ:
            last_updated_time = datetime.datetime.strptime(os.environ[JWT_PUBLIC_KEY_LAST_UPDATED_TIME_ENV_NAME], "%Y-%m-%d %H:%M:%S.%f")

        if last_updated_time and last_updated_time > datetime.datetime.utcnow() - datetime.timedelta(days = 1):
            return json.loads(os.environ[JWT_PUBLIC_KEYS_ENV_NAME])
        else:
            return json.loads(AuthenticationHelper.refresh_keys())

    @staticmethod
    def refresh_keys():
        response = requests.get(OPENID_CONFIGURATION_URL)
        if response.status_code == 200:
            openid_config = response.json()
            response = requests.get(openid_config["jwks_uri"])
            if response.status_code == 200:
                jwt_public_keys = os.environ.setdefault(JWT_PUBLIC_KEYS_ENV_NAME, response.text)
                os.environ.setdefault(JWT_PUBLIC_KEY_LAST_UPDATED_TIME_ENV_NAME, str(datetime.datetime.utcnow()))
                return jwt_public_keys
        raise LunaServerException("Cannot refresh public keys for AAD auth. Response status code {} Error {}".format(response.status_code, response.text))

    @staticmethod
    def get_kid(token):
        headers = jwt.get_unverified_header(token)
        if not headers:
            raise InvalidAuthorizationToken('missing headers')
        try:
            return headers['kid']
        except KeyError:
            raise InvalidAuthorizationToken('missing kid')

    @staticmethod
    def get_alg(token):
        headers = jwt.get_unverified_header(token)
        if not headers:
            raise InvalidAuthorizationToken('missing headers')
        try:
            return headers['alg']
        except KeyError:
            raise InvalidAuthorizationToken('missing alg')
    
    @staticmethod
    def get_jwk(kid):
        for jwk in AuthenticationHelper.get_keys().get('keys'):
            if jwk.get('kid') == kid:
                return jwk
        raise InvalidAuthorizationToken('kid not recognized')

    @staticmethod
    def decode_value(val):
        decoded = base64.urlsafe_b64decode(AuthenticationHelper.ensure_bytes(val) + b'==')
        return int.from_bytes(decoded, 'big')

    @staticmethod
    def get_public_key(token):
        return AuthenticationHelper.rsa_pem_from_jwk(AuthenticationHelper.get_jwk(AuthenticationHelper.get_kid(token)))

    @staticmethod
    def ensure_bytes(key):
        if isinstance(key, str):
            key = key.encode('utf-8')
        return key

    @staticmethod
    def rsa_pem_from_jwk(key):
        return RSAPublicNumbers(
            n=AuthenticationHelper.decode_value(key['n']),
            e=AuthenticationHelper.decode_value(key['e'])
        ).public_key(default_backend()).public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    @staticmethod
    def ValidateSigniture(token):
        try:
            return jwt.decode(token,
                AuthenticationHelper.get_public_key(token),
                verify=True,
                algorithms=[AuthenticationHelper.get_alg(token)],
                audience=os.environ['AAD_VALID_AUDIENCES'].split(";"),
                issuer=os.environ['AAD_TOKEN_ISSUER'])
            
        except Exception as e:
            raise LunaUserException(HTTPStatus.FORBIDDEN, "The AAD token signiture is invalid.")

    @staticmethod
    def ValidateSignitureAndAdmin(token):
        signiture = AuthenticationHelper.ValidateSigniture(token)
        for admin in AgentUser.ListAllAdmin():
            ## TODO: which property should we use here
            if signiture["oid"].lower() == admin.ObjectId.lower():
                return "Admin"
        
        raise LunaUserException(HTTPStatus.FORBIDDEN, "Admin permission is required for this operation.")

    @staticmethod
    def ValidateSignitureAndUser(token, subscriptionId=None):
        signiture = AuthenticationHelper.ValidateSigniture(token)
        objectId = signiture["oid"].lower()
        for user in AgentUser.ListAllAdmin():
            ## TODO: which property should we use here
            if objectId == user.ObjectId.lower():
                return "Admin"

        ## If the subscription id is specified, validate the user permission. Otherwise, return user name directly
        if subscriptionId:
            for user in AgentUser.ListAllBySubscriptionId(subscriptionId):
                if objectId == user.ObjectId.lower():
                    return objectId

            raise LunaUserException(HTTPStatus.FORBIDDEN, "The resource doesn't exist or you don't have permission to access it.")
        else:
            return objectId

    @staticmethod
    def GetUserObjectId(token):
        signiture = AuthenticationHelper.ValidateSigniture(token)
        return signiture["oid"].lower()