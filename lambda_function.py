import boto3
import json
import os
import time
import urllib.request
import urllib.parse
import uuid

ALEXA_CLIENT_ID = os.environ["ALEXA_CLIENT_ID"]
ALEXA_CLIENT_SECRET = os.environ["ALEXA_CLIENT_SECRET"]
DEVICE_MAC_ADDRESS = os.environ["DEVICE_MAC_ADDRESS"]
DEVICE_NAME = os.environ["DEVICE_NAME"]
ENDPOINT_ID = "my_endpoint"
SESSION_ID = "my_session"

def lambda_handler(event, context):
    print("event: %s" % event)
    
    directive_namespace = event["directive"]["header"]["namespace"]
    directive_name = event["directive"]["header"]["name"]

    if directive_namespace == "Alexa.Authorization" and directive_name == "AcceptGrant":
        response = handle_authorization(event)
    elif directive_namespace == "Alexa.Discovery" and directive_name == "Discover":
        response = handle_discovery(event)
    elif directive_namespace == "Alexa.PowerController" and directive_name == "TurnOn":
        response = handle_turn_on(event)
    else:
        response = handle_error(event)
    
    print("response: %s" % response)
    return response

def handle_authorization(event):
    # Alexaイベント送信用のトークン取得
    method = "POST"
    url = "https://api.amazon.com/auth/o2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": event["directive"]["payload"]["grant"]["code"],
        "client_id": ALEXA_CLIENT_ID,
        "client_secret": ALEXA_CLIENT_SECRET,
    })
    req = urllib.request.Request(url, data = data.encode(), headers = headers, method = method)
    with urllib.request.urlopen(req) as res:
        body = json.loads(res.read())
        print("alexa token: %s" % body)
    # 取得したトークンを保存
    db = boto3.resource("dynamodb")
    table = db.Table("alexa_wol_sessions")
    table.update_item(
        Key = {"id": SESSION_ID},
        UpdateExpression = "set alexa_token = :alexa_token",
        ExpressionAttributeValues = {":alexa_token": body}
    )
    # AcceptGrant.Responseイベントを返す
    response = {
        "event": {
            "header": {
                "namespace": "Alexa.Authorization",
                "name": "AcceptGrant.Response",
                "payloadVersion": "3",
                "messageId": get_uuid(),
            },
            "payload": {},
        }
    }
    return response

def handle_discovery(event):
    # Discover.Responseイベントでデバイス情報を返す
    response = {
        "event": {
            "header": {
                "namespace": "Alexa.Discovery",
                "name": "Discover.Response",
                "payloadVersion": "3",
                "messageId": get_uuid(),
            },
            "payload": {
                "endpoints": [
                    {
                        "endpointId": ENDPOINT_ID,
                        "manufacturerName": "algilab",
                        "friendlyName": DEVICE_NAME,
                        "description": "デバイスのWoLスイッチ",
                        "displayCategories": ["SWITCH"],
                        "cookie": {},
                        "capabilities": [
                            {
                                "type": "AlexaInterface",
                                "interface": "Alexa",
                                "version": "3",
                            },
                            {
                                "type": "AlexaInterface",
                                "interface": "Alexa.PowerController",
                                "version": "3",
                                "properties": {
                                    "supported": [
                                        {
                                            "name": "powerState",
                                        }
                                    ],
                                    ## FalseにするとAlexaがReportStateディレクティブを送信しない
                                    ## アプリ上ではスイッチの状態を表示しなくなる
                                    "retrievable": False,
                                }
                            },
                            {
                                "type": "AlexaInterface",
                                "interface": "Alexa.WakeOnLANController",
                                "version": "3",
                                "properties": {},
                                "configuration": {
                                    "MACAddresses": [
                                        DEVICE_MAC_ADDRESS,
                                    ]
                                }
                            }
                        ]
                    }
                ]
            }
        }
    }
    return response

def handle_turn_on(event):
    # Alexaイベント送信用のトークン更新
    db = boto3.resource("dynamodb")
    table = db.Table("alexa_wol_sessions")
    query_data = table.get_item(
        Key = {"id": SESSION_ID}
    )
    print("session: %s" % query_data["Item"])
    method = "POST"
    url = "https://api.amazon.com/auth/o2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": query_data["Item"]["alexa_token"]["refresh_token"],
        "client_id": ALEXA_CLIENT_ID,
        "client_secret": ALEXA_CLIENT_SECRET,
    })
    req = urllib.request.Request(url, data = data.encode(), headers = headers, method = method)
    with urllib.request.urlopen(req) as res:
        body = json.loads(res.read())
        print("alexa token: %s" % body)
    # 取得したトークンを保存
    table.update_item(
        Key = {"id": SESSION_ID},
        UpdateExpression = "set alexa_token = :alexa_token",
        ExpressionAttributeValues = {":alexa_token": body}
    )
    access_token = body["access_token"]
    # WakeUPイベント送信
    ## DeferredResponseイベントを送信しなくても問題なく動作したので
    ## WakeUPイベント送信後にResponseイベントを同期送信する
    method = "POST"
    url = "https://api.fe.amazonalexa.com/v3/events"
    headers = {
        "Authorization": "Bearer %s" % access_token,
        "Content-Type": "application/json",
    }
    data = json.dumps({
        "event": {
            "header": {
                "namespace": "Alexa.WakeOnLANController",
                "name": "WakeUp",
                "payloadVersion": "3",
                "messageId": get_uuid(),
                "correlationToken": event["directive"]["header"]["correlationToken"],
            },
            "endpoint": {
                "scope": {
                    "type": "BearerToken",
                    "token": access_token,
                },
                "endpointId": event["directive"]["endpoint"]["endpointId"],
            },
            "payload": {},
        },
        "context": {
            "properties": [
                {
                    "namespace": "Alexa.PowerController",
                    "name": "powerState",
                    "value": "OFF",
                    "timeOfSample": get_utc_timestamp(),
                    "uncertaintyInMilliseconds": 500,
                },
            ],
        },
    })
    req = urllib.request.Request(url, data = data.encode(), headers = headers, method = method)
    with urllib.request.urlopen(req) as res:
        body = res.read()
        print("alexa event response: %s %s" % (res.status, body))
    # Responseイベントを返す
    response = {
        "event": {
            "header": {
                "namespace": "Alexa",
                "name": "Response",
                "payloadVersion": "3",
                "messageId": get_uuid(),
                "correlationToken": event["directive"]["header"]["correlationToken"],
            },
            "endpoint": {
                "endpointId": event["directive"]["endpoint"]["endpointId"],
            },
            "payload": {}
        },
        "context": {
            "properties": [
                {
                    "namespace": "Alexa.PowerController",
                    "name": "powerState",
                    "value": "ON",
                    "timeOfSample": get_utc_timestamp(),
                    "uncertaintyInMilliseconds": 500,
                }
            ]
        },
    }
    return response

def handle_error(event):
    response = {
        "event": {
            "header": {
                "namespace": "Alexa",
                "name": "ErrorResponse",
                "payloadVersion": "3",
                "messageId": get_uuid(),
            },
            "endpoint": {
                "endpointId": event["directive"]["endpoint"]["endpointId"],
            },
            "payload": {
                "type": "INVALID_DIRECTIVE",
                "message": "サポートされていないディレクティブです"
            }
        },
    }
    return response

def get_utc_timestamp(seconds=None):
    return time.strftime("%Y-%m-%dT%H:%M:%S.00Z", time.gmtime(seconds))

def get_uuid():
    return str(uuid.uuid4())
