# Harmony PushKit

This is a very early experimental Home Assistant integration and may change substantially.

## Approach

The HarmonyOS app reports only `app_data.pushkit_token` through its `mobile_app` registration. The integration discovers valid tokens, creates a notify entity for each device, and sends notifications through the selected entity.

The integration obtains a Connect API access token using local AGC client credentials, uses that token to request a short-lived PushKit ticket from a cloud function, and then calls the Push v3 API with the issued ticket. Tokens are cached while valid and checked before use.

Notifications are delivered normally by default. Enabling App persistence also writes the notification to the app notification history.

## Why This Design

We do not want to distribute service-account JWTs with overly broad permissions to end users. The cloud ticket service can constrain issuance and ticket lifetime, while allowing the minimum-permission model to evolve independently.

Because of current Huawei capabilities and processes, we cannot yet publicly provide all required credentials. We are working with Huawei toward credentials limited to push-notification use.

## Current Limits

To reduce accidental abuse during testing, each PushKit token is limited to 20 send attempts per local calendar day. The limit exists only in the current HA process, resets after restart, and is not shared between HA instances. It is a goodwill anti-abuse measure, not a security or authorization boundary.

Please do not abuse or maliciously use push notifications. Abnormal push activity may trigger Huawei Push Kit risk controls, causing serious harm to the project and potentially resulting in the app being removed from distribution. This is not an outcome we want.

Community testers can receive a dedicated test key for requesting tickets from the signing service. Join the QQ group: `110658353`, or contact `43355621@qq.com`.

中文: [README.md](README.md)
