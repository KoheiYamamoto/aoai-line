import logging, os, uuid, openai
import azure.functions as func
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import azure.cosmos as cosmos_client

# get environment variables
channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
openai.api_type = "azure"
openai.api_version = os.getenv('AOAI_API_VERSION', None)
openai.api_base = os.getenv('AOAI_BASE', None)
openai.api_key = os.getenv('AOAI_APIKEY', None) 
cosmos_uri = os.getenv('COSMOS_URI', None)
cosmos_key = os.getenv('COSMOS_KEY', None)
cosmos_db_name = 'Test'
cosmos_container_name = 'Items'

# create instance
line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

def chatGPT(input_txt):
    response = openai.ChatCompletion.create(
        engine="gpt-35-turbo", # engine = "deployment_name"
        messages = [
            {"role":"system","content":"あなたは友達と話すような返答を行ってください。\n構文の特徴は以下の通りです。\n- 一切、敬語を使わない\n- タメ口で話す\n- 適度に絵文字を使う\n- 250文字を超えてはいけない"},
            {"role":"user","content":"明日何しようかな"},
            {"role":"assistant","content":"お天気☀️もいいし、公園でピクニックでもしない？🥺 \nそれとも、映画を観に行くとかどう？🍿"},
            {"role": "user", "content": input_txt},
        ],
        temperature=0.7,
        max_tokens=800,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None)
    return response['choices'][0]['message']['content']

def insertCosmosDB(user_id, input_txt, output_txt):
    try:
        client = cosmos_client.CosmosClient(cosmos_uri, credential=cosmos_key)
        database_client = client.get_database_client(cosmos_db_name)
        container_client = database_client.get_container_client(cosmos_container_name)
        container_client.upsert_item({
                'id': str(uuid.uuid4()),
                'userId': user_id,
                'Q': str(input_txt),
                'A': str(output_txt)
        })
        logging.info('Project details are stored to Cosmos DB.')
    except Exception as e:
        logging.error(e)

@handler.add(MessageEvent, message=TextMessage)
def message_text(event):
    output_txt = chatGPT(event.message.text)
    logging.info("chatGPT: " + output_txt)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=output_txt)
    )
    insertCosmosDB(event.source.user_id, event.message.text, output_txt)

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    # get x-line-signature header value
    signature = req.headers['x-line-signature']
    # get request body as text
    body = req.get_body().decode("utf-8")
    logging.info("Request body: " + body)
    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        func.HttpResponse(status_code=400)
    return func.HttpResponse('OK', status_code=200)
