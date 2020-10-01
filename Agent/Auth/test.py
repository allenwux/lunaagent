import base64
from jwt import decode
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

def ensure_bytes(key):
    if isinstance(key, str):
        key = key.encode('utf-8')
    return key


def decode_value(val):
    decoded = base64.urlsafe_b64decode(ensure_bytes(val) + b'==')
    return int.from_bytes(decoded, 'big')

def rsa_pem_from_jwk():
    return RSAPublicNumbers(
        n=decode_value(jwts["keys"][0]['n']),
        e=decode_value(jwts["keys"][0]['e'])
    ).public_key(default_backend()).public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImtpZCI6ImppYk5ia0ZTU2JteFBZck45Q0ZxUms0SzRndyJ9.eyJhdWQiOiI5MzQ4YTQ4YS05Zjk3LTRlOWUtYmNlMi00MGQyMzk4NDA3MzMiLCJpc3MiOiJodHRwczovL2xvZ2luLm1pY3Jvc29mdG9ubGluZS5jb20vNzJmOTg4YmYtODZmMS00MWFmLTkxYWItMmQ3Y2QwMTFkYjQ3L3YyLjAiLCJpYXQiOjE2MDAzNzUyMDcsIm5iZiI6MTYwMDM3NTIwNywiZXhwIjoxNjAwMzc5MTA3LCJhaW8iOiJBVlFBcS84UUFBQUFaL1Z4dFl6ZWRPcGtBKzFwVFZMdjNkNnhzOUdjY3hHVVdiYjc0cHl5SVpwYVlNUGhUbVhsUUJXTDlEajNMSlVtR0FrbmdvelNHbFgzN1NVdFVWZnM1YXhtU0I0Qms5dXAyQUZuR0xNclpnST0iLCJuYW1lIjoiQ2hhZCBBZGFtcyIsIm5vbmNlIjoiODFjMmZmNTctNjNmZS00MTlmLWFiODMtMTVlOThjZjk5MDMxIiwib2lkIjoiNmQyN2U2MTItNTcyOS00MjJhLTgyNTctOTljZGE3ZmExMzJmIiwicHJlZmVycmVkX3VzZXJuYW1lIjoiY2hhZGFkYUBtaWNyb3NvZnQuY29tIiwicmgiOiIwLkFSb0F2NGo1Y3ZHR3IwR1JxeTE4MEJIYlI0cWtTSk9YbjU1T3ZPSkEwam1FQnpNYUFQUS4iLCJzdWIiOiJ0ZVhpdHFqdG9vaGZkUFA2czQ1bFBlZS1HWU5RdWtsbTdnNXZrZXo5V0pjIiwidGlkIjoiNzJmOTg4YmYtODZmMS00MWFmLTkxYWItMmQ3Y2QwMTFkYjQ3IiwidXRpIjoiUnlUYXhBLXVIMGlzX2ZmVEh2Y0RBQSIsInZlciI6IjIuMCJ9.AE4rAtZCcPyK6axQWTuJDrk56u-epxbFfWzUFod266-DswbR8558HAKiOLJls7KvV7_ssYeipM7U0ZU6pmN7fFiLjmNHNyCXWE8Dqixn6hJno1_Ik1DAn5k-imF2CrBYrmb9ZkSSIZzy6fYcK5FPVDXvVd4KS2zfEiel8eoVUzEK31wudkImZacy6qafkNIeLcno28VH2Jt9ESoTD3fJ8-nFOorMmOWOeXk1YuXktvAZiTQfatAUAxhwvQg5RxkZuAMHr9sHJqb23Rylh489pQQ7FZKGBqhY-zpp7G1rytguz8wpmhctgJRHu6kmQsVNfih2AfCE3d-mt27vEOueNA"
#token = "eyJ0eXAiOiJKV1QiLCJub25jZSI6IlhzekE5SUNlR2RadFUtMXFjRk9LVHVwWW8zR0NYa1FEaVY1QlJGMlk2SWMiLCJhbGciOiJSUzI1NiIsIng1dCI6ImppYk5ia0ZTU2JteFBZck45Q0ZxUms0SzRndyIsImtpZCI6ImppYk5ia0ZTU2JteFBZck45Q0ZxUms0SzRndyJ9.eyJhdWQiOiIwMDAwMDAwMy0wMDAwLTAwMDAtYzAwMC0wMDAwMDAwMDAwMDAiLCJpc3MiOiJodHRwczovL3N0cy53aW5kb3dzLm5ldC83MmY5ODhiZi04NmYxLTQxYWYtOTFhYi0yZDdjZDAxMWRiNDcvIiwiaWF0IjoxNjAwMzc0NzYyLCJuYmYiOjE2MDAzNzQ3NjIsImV4cCI6MTYwMDM3ODY2MiwiYWNjdCI6MCwiYWNyIjoiMSIsImFpbyI6IkFWUUFxLzhRQUFBQW9UK2NkZDduZWtyWlE2aDc3OG00b3g4RDFsSnhJelhuVUpGZzdEQVFUR0FZU1Q4eHRFSVMrUEU4aE43RTY5bHBnamgwT0p0TUZybE5HcVdvSndOY2h1T3I2ZTVvVGZmK1JYQUtUc2tKTlhVPSIsImFtciI6WyJ3aWEiLCJtZmEiXSwiYXBwX2Rpc3BsYXluYW1lIjoibHVuYS1zYSIsImFwcGlkIjoiOTM0OGE0OGEtOWY5Ny00ZTllLWJjZTItNDBkMjM5ODQwNzMzIiwiYXBwaWRhY3IiOiIwIiwiZmFtaWx5X25hbWUiOiJBZGFtcyIsImdpdmVuX25hbWUiOiJDaGFkIiwiaWR0eXAiOiJ1c2VyIiwiaW5fY29ycCI6InRydWUiLCJpcGFkZHIiOiIxMzYuMzUuMTgyLjE4NiIsIm5hbWUiOiJDaGFkIEFkYW1zIiwib2lkIjoiNmQyN2U2MTItNTcyOS00MjJhLTgyNTctOTljZGE3ZmExMzJmIiwib25wcmVtX3NpZCI6IlMtMS01LTIxLTEyNDUyNTA5NS03MDgyNTk2MzctMTU0MzExOTAyMS0xNTQyMzgwIiwicGxhdGYiOiIzIiwicHVpZCI6IjEwMDNCRkZEOTE1NDg3MjAiLCJyaCI6IjAuQVJvQXY0ajVjdkdHcjBHUnF5MTgwQkhiUjRxa1NKT1huNTVPdk9KQTBqbUVCek1hQVBRLiIsInNjcCI6Im9wZW5pZCBwcm9maWxlIFVzZXIuUmVhZCBVc2VyLlJlYWRCYXNpYy5BbGwgZW1haWwiLCJzaWduaW5fc3RhdGUiOlsia21zaSJdLCJzdWIiOiJOMWVwVFF2Y24zX2ZjelNPalJhRVZsVXU1WlBEM19sYVU2V3FmendHNmZrIiwidGVuYW50X3JlZ2lvbl9zY29wZSI6IldXIiwidGlkIjoiNzJmOTg4YmYtODZmMS00MWFmLTkxYWItMmQ3Y2QwMTFkYjQ3IiwidW5pcXVlX25hbWUiOiJjaGFkYWRhQG1pY3Jvc29mdC5jb20iLCJ1cG4iOiJjaGFkYWRhQG1pY3Jvc29mdC5jb20iLCJ1dGkiOiJua0VBbWlDTlhFZVRHS0RYbENJTEFBIiwidmVyIjoiMS4wIiwieG1zX3N0Ijp7InN1YiI6InRlWGl0cWp0b29oZmRQUDZzNDVsUGVlLUdZTlF1a2xtN2c1dmtlejlXSmMifSwieG1zX3RjZHQiOjEyODkyNDE1NDd9.TFl8zLuGlljFZxvKRwsJOzpB5y2Lzk4ddxPTt-Ywx-eL9no6GeHljac_isJqrmu2SUWUEKKo4ZnnGFfUE4_vy4id-pP3PMHoVfGUu6R5Yos5WKviUTvoKHNMc0D1YNigMZQTm0jjewDce4HecKk0FXhMwSPOUSSXAtpLV7LF7vPWNT9Fp4MpIXOLPs6m5rWBcBLnMMv770rhw-6R2wPgMqdDVDHU8eX8pN4JUiCLGLkItqpm68DsInkD5FVJ2hskP2aKmh77i3Ps6b0s5_3C78HaiJy9Yv4ilkE6reqvpUrZkRzB6s_EaP8LXm14412sX3AprURUuL1EN-DFsDDT1Q"
sections = token.split(".")

print(sections[0])
print("==================================")
print(sections[1])
print("==================================")
print(sections[2])

print(base64.urlsafe_b64decode(sections[0].encode('utf-8') + b'=='))
print(base64.urlsafe_b64decode(sections[1].encode('utf-8') + b'=='))

jwts = {"keys":[
    {"kty":"RSA",
    "use":"sig",
    "kid":"jibNbkFSSbmxPYrN9CFqRk4K4gw",
    "x5t":"jibNbkFSSbmxPYrN9CFqRk4K4gw",
    "n":"2YX-YDuuTzPiaiZKt04IuUzAjCjPLLmBCVA6npKuZyIouMuaSEuM7BP8QctfCprUY16Rq2-KDrAEvaaKJvsD5ZONddt79yFdCs1E8wKlYIPO74fSpePdVDizflr5W-QCFH9tokbZrHBBuluFojgtbvPMXAhHfZTGC4ItZ0i_Lc9eXwtENHJQC4e4m7olweK1ExM-OzsKGzDlOsOUOU5pN2sHY74nXPqQRH1dQKfB0NT0YrfkbnR8fiq8z-soixfECUXkF8FzWnMnqL6X90wngnuIi8OtH2mvDcnsvUVh3K2JgvSgjRWZbsDx6G-mVQL2vEuHXMXoIoe8hd1ZpV16pQ",
    "e":"AQAB",
    "x5c":["MIIDBTCCAe2gAwIBAgIQUUG7iptQUoVA7bYvX2tHlDANBgkqhkiG9w0BAQsFADAtMSswKQYDVQQDEyJhY2NvdW50cy5hY2Nlc3Njb250cm9sLndpbmRvd3MubmV0MB4XDTIwMDcxODAwMDAwMFoXDTI1MDcxODAwMDAwMFowLTErMCkGA1UEAxMiYWNjb3VudHMuYWNjZXNzY29udHJvbC53aW5kb3dzLm5ldDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBANmF/mA7rk8z4momSrdOCLlMwIwozyy5gQlQOp6SrmciKLjLmkhLjOwT/EHLXwqa1GNekatvig6wBL2miib7A+WTjXXbe/chXQrNRPMCpWCDzu+H0qXj3VQ4s35a+VvkAhR/baJG2axwQbpbhaI4LW7zzFwIR32UxguCLWdIvy3PXl8LRDRyUAuHuJu6JcHitRMTPjs7Chsw5TrDlDlOaTdrB2O+J1z6kER9XUCnwdDU9GK35G50fH4qvM/rKIsXxAlF5BfBc1pzJ6i+l/dMJ4J7iIvDrR9prw3J7L1FYdytiYL0oI0VmW7A8ehvplUC9rxLh1zF6CKHvIXdWaVdeqUCAwEAAaMhMB8wHQYDVR0OBBYEFFOUEOWLUJOTFTOlr7P+6GxsmM90MA0GCSqGSIb3DQEBCwUAA4IBAQCP+LLZw7SSYnWQmRGWHmksBwwJ4Gy32C6g7+wZZv3ombHW9mwLQuzsir97/PP042i/ZIxePHJavpeLm/z3KMSpGIPmiPtmgNcK4HtLTEDnoTprnllobOAqU0TREFWogjkockNo98AvpsmHxNMXuwDikto9o/d9ACBtpkpatS2xgVOZxZtqyMpwZzSJARD5A4qcKov4zdqntVyjpZGK4N6ZaedRbEVd12m1VI+dtDB9+EJRqtTn8zamPYljVTEPNCbDAFgKBDtrhwBnrrrnKTq4/LEOouNQZuUucBTMOGDn4FEejNh3qbxNdWR6tSZbXUnJ+NIQ99IqZMvvMqm9ndL7"]
    ,"issuer":"https://login.microsoftonline.com/{tenantid}/v2.0"}
]}

valid_audiences = "52ed21f2-32e1-4df0-86be-00f5795e7137"
issuer = "https://login.microsoftonline.com/72f988bf-86f1-41af-91ab-2d7cd011db47/v2.0"

decoded = decode(token,
                rsa_pem_from_jwk(),
                verify=True,
                algorithms=['RS256'],
                audience=valid_audiences,
                issuer=issuer)

print(decoded)