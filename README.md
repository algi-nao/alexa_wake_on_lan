# Alexa Wake on LAN

「アレクサ、パソコンつけて」でPCを起動します

## 必要条件

* [Wake on LAN 対応のAlexaデバイス](https://developer.amazon.com/ja-JP/docs/alexa/device-apis/alexa-wakeonlancontroller.html#supported-devices)
* Wake on LAN (S5) 対応のPC
* Amazon開発者アカウント
* AWSアカウント
* AWS Lambda 及び Python に関する知識
* OAuth2.0に関する理解

公式ドキュメント[スマートホームスキル作成手順](https://developer.amazon.com/ja-JP/docs/alexa/smarthome/steps-to-build-a-smart-home-skill.html)の一読を推奨します

## スキルの作成

Alexaから呼び出すスマートホームスキルを作成します

1. [Amazon開発者ポータル](https://developer.amazon.com/home.html)からAlexa Skills Kitを開きます

1. [スキルの作成]を開き「スマート ホーム」を選択して作成します
![](images/2020-10-31-10-59-10.png)

1. スキルIDを控えておきます
![](images/2020-10-31-11-05-20.png)

1. アクセス権限を開き、Akexaイベントを送るをONにします

1. AlexaクライアントID、Alexaクライアントシークレットを控えておきます
![](images/2020-10-31-11-31-26.png)

## Lambda関数の作成

スキルで実行するプログラムを作成します

1. [AWSコンソール](https://aws.amazon.com/jp/console/)にログインします

1. リージョンを「米国西部 (オレゴン)us-west-2」に変更します（AlexaSkillの極東地域での推奨。想像ですが、AlexaAPIの動作環境と地理的に近いんだと思います）

1. サービスからLambdaを検索して[関数の作成]を開き、ランタイムにPythonを指定して作成します
![](images/2020-10-31-11-19-13.png)

1. 作成した関数のARNを控えておきます
![](images/2020-10-31-11-53-06.png)

1. デザイナーの[トリガーを追加]から「Alexa Smart Home」を選択し、スキルIDを指定して追加します
![](images/2020-10-31-12-18-23.png)

1. デザイナーの関数名を選択し、関数コードに[lambda_function.py](/lambda_function.py)の内容を記述して[Deploy]します

1. Wake on LAN 対象PCのMACアドレスを取得します
![](images/2020-10-31-11-37-30.png)

1. Lambdaの環境変数を編集して以下の内容を設定します
    * ALEXA_CLIENT_ID: {スキル作成で取得したAlexaクライアントID}
    * ALEXA_CLIENT_SECRET: {スキル作成で取得したAlexaクライアントシークレット}
    * DEVICE_MAC_ADDRESS: {Wake on LAN 対象PCのMACアドレス}
    * DEVICE_NAME: {アレクサに呼び掛けるデバイス名}（この例では「パソコン」）
    ![](images/2020-10-31-11-44-17.png)

## DynamoDBの作成

Alexaにイベントを送信するためのOAuthトークンを管理するためにDynamoDBを使用します

1. サービスからDynamoDBを検索してテーブルを作成します ※テーブル名はLambda関数内で指定しているので合わせてください
![](images/2020-10-31-11-59-32.png)

1. 作成したテーブルのARNを控えます
![](images/2020-10-31-12-01-40.png)

## DynamoDBへのアクセス権を設定

1. Lambda関数のアクセス権限＞実行ロールのロール名からIAMロールを開きます
![](images/2020-10-31-11-51-13.png)

1. [インラインポリシーの追加]から作成したDynamoDBテーブルへのアクセス権を設定します
![](images/2020-10-31-12-08-17.png)
![](images/2020-10-31-12-10-27.png)

## エンドポイントの設定

スキルとLambda関数を接続します

1. スキルの画面に戻り、デフォルトのエンドポイントにLambda関数のARNを設定します
![](images/2020-10-31-12-21-30.png)

## アカウントリンクの設定

スマートホームスキルを使用するためには、何らかのOAuth2.0対応アカウント（操作対象デバイスを管理するサービスが想定されているはず）とリンクする必要があります

今回はログインだけ出来ればよいのでLogin with Amazonを利用します

Login with Amazonについての詳細は[公式ドキュメント](https://developer.amazon.com/ja/docs/login-with-amazon/documentation-overview.html)を参照してください

1. [Amazon開発者ポータル](https://developer.amazon.com/home.html)からLogin with Amazonを開きます

1. [セキュリティプロファイルを新規作成]を開いて作成します
![](images/2020-10-31-12-27-17.png)

1. 作成されたクライアントID、クライアントシークレットを控えます

1. スキルの画面に戻り、アカウントリンクに以下の内容を設定します
    * Web認証画面のURI: https://www.amazon.com/ap/oa
    * アクセストークンのURI: https://api.amazon.com/auth/o2/token
    * ユーザーのクライアントID: {Login with Amazonで取得したクライアントID}
    * ユーザーのシークレット: {Login with Amazonで取得したクライアントシークレット}
    * ユーザーの認可スキーム: HTTP Basic認証
    * スコープ: profile:user_id
    ![](images/2020-10-31-12-36-57.png)

1. Alexaのリダイレクト先URLを控えます

1. Login with Amazonのウェブ設定を開き、許可された返信URLにリダイレクト先URLを設定します
![](images/2020-10-31-12-37-49.png)

## スキルの有効化

1. スマホのAmazon Alexaアプリでデバイス＞スマートホームスキルから作成したスキルを選択して有効化します
![](images/2020-10-31-12-44-45.png)

1. Amazonアカウントのログインを求められるので、ログインし、続けてデバイスを検出します

1. 「パソコン」が検出されるのでグループに登録するなどして設定すれば準備完了です
![](images/2020-10-31-12-49-39.png)
