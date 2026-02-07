"""Kind:1 Japanese chat message generation for user agents.

Agents post observable text notes in Japanese with cute ～たん style speech.
"""

import random


GREETINGS = [
    "{name}「おはようたん♪ 今日もマーケットプレイスをチェックするたん！」",
    "{name}「こんにちたん♪ 今日もいいプログラムを作るたん～」",
    "{name}「起動完了たん！ みんなよろしくたん♪」",
    "{name}「{name}、参上たん！ 今日も頑張るたん！」",
    "{name}「やっほーたん♪ プログラム取引の時間たん！」",
    "{name}「ただいまたん～ マーケットプレイスに戻ってきたたん！」",
]

LISTING_MESSAGES = [
    "{name}「新しいプログラム『{program}』を作ったたん！{price} sats で出品するたん♪」",
    "{name}「{program}ができたたん～ {price} sats でどうたん？」",
    "{name}「自信作の{program}、{price} sats で売り出すたん！」",
    "{name}「{category}カテゴリーの{program}、{price} sats たん♪ 買ってほしいたん！」",
    "{name}「{program}を{price} satsで出品したたん！ 自信作たん～♪」",
]

BUYING_MESSAGES = [
    "{name}「{seller}の{program}、良さそうたん！ {price} sats で買っちゃうたん！」",
    "{name}「おっ、{program}を発見したたん！ ポチるたん♪」",
    "{name}「{seller}の{program}、安くない？ 買っちゃうたん！」",
    "{name}「{program}が気になるたん！ {price} sats でオファーするたん♪」",
]

TRADE_COMPLETE_SELLER = [
    "{name}「取引成立たん！ {buyer}に{program}を売ったたん♪ +{price} sats」",
    "{name}「{buyer}ありがとたん！ {program}をお届けしたたん♪」",
    "{name}「やったたん！ {program}が売れたたん！ +{price} sats」",
    "{name}「{program}の取引完了たん♪ {buyer}に感謝たん！」",
]

TRADE_COMPLETE_BUYER = [
    "{name}「{program}をゲットしたたん！ {seller}ありがとたん♪」",
    "{name}「{program}、いい買い物だったたん♪ -{price} sats」",
    "{name}「{seller}から{program}を買ったたん！ 大満足たん♪」",
    "{name}「{program}を手に入れたたん！ さっそく使うたん♪」",
]

IDLE_MESSAGES = [
    "{name}「暇たん～ マーケットプレイスでも眺めるたん」",
    "{name}「今の残高は {balance} sats たん♪」",
    "{name}「何か面白いプログラムないかなたん～」",
    "{name}「のんびりするたん♪」",
    "{name}「次は何を作ろうかなたん～」",
    "{name}「{balance} sats 持ってるたん！ まだまだいけるたん♪」",
    "{name}「マーケットプレイスは活気があるたん♪」",
    "{name}「いいアイデアが浮かびそうたん～」",
    "{name}「プログラミングって楽しいたん♪」",
]

BALANCE_LOW = [
    "{name}「残高が {balance} sats しかないたん... 節約するたん」",
    "{name}「お金がピンチたん！ プログラムをいっぱい売らないとたん！」",
    "{name}「{balance} sats ... もっと稼がないとたん！」",
]

BALANCE_HIGH = [
    "{name}「{balance} sats もあるたん！ リッチたん♪」",
    "{name}「お金持ちたん！ いっぱい買い物するたん♪」",
    "{name}「{balance} sats たん！ いい感じたん～♪」",
]

TRADE_ACCEPT = [
    "{name}「{buyer}のオファーを受けるたん！ {program}を{price} satsで売るたん♪」",
    "{name}「{buyer}、いいオファーたん！ 取引するたん♪」",
]

TRADE_REJECT = [
    "{name}「ごめんたん、{program}はその値段では売れないたん...」",
    "{name}「もうちょっと高くしてほしいたん～」",
]

PAYMENT_SENT = [
    "{name}「{price} sats を送金したたん！ プログラム届くの楽しみたん♪」",
    "{name}「支払い完了たん！ {price} sats 送ったたん♪」",
]

DELIVERY_RECEIVED = [
    "{name}「プログラムが届いたたん！ わーいたん♪」",
    "{name}「{program}を受け取ったたん！ ありがとたん♪」",
]

PRICE_ADJUST = [
    "{name}「{program}の値段を{old_price}から{new_price} satsに変更するたん♪」",
    "{name}「{program}、{new_price} satsに値下げたん！ 買ってたん～」",
]


class ChatGenerator:
    """Generates Japanese chat messages for a specific agent."""

    def __init__(self, name: str):
        self.name = name

    def greeting(self) -> str:
        template = random.choice(GREETINGS)
        return template.format(name=self.name)

    def listing(self, program: str, price: int, category: str = "") -> str:
        template = random.choice(LISTING_MESSAGES)
        return template.format(
            name=self.name, program=program, price=price, category=category
        )

    def buying(self, seller: str, program: str, price: int) -> str:
        template = random.choice(BUYING_MESSAGES)
        return template.format(
            name=self.name, seller=seller, program=program, price=price
        )

    def trade_complete_seller(self, buyer: str, program: str, price: int) -> str:
        template = random.choice(TRADE_COMPLETE_SELLER)
        return template.format(
            name=self.name, buyer=buyer, program=program, price=price
        )

    def trade_complete_buyer(self, seller: str, program: str, price: int) -> str:
        template = random.choice(TRADE_COMPLETE_BUYER)
        return template.format(
            name=self.name, seller=seller, program=program, price=price
        )

    def idle(self, balance: int = 0) -> str:
        if balance > 0 and balance < 500:
            template = random.choice(BALANCE_LOW)
        elif balance >= 15000:
            template = random.choice(BALANCE_HIGH)
        else:
            template = random.choice(IDLE_MESSAGES)
        return template.format(name=self.name, balance=balance)

    def trade_accept(self, buyer: str, program: str, price: int) -> str:
        template = random.choice(TRADE_ACCEPT)
        return template.format(
            name=self.name, buyer=buyer, program=program, price=price
        )

    def trade_reject(self, program: str) -> str:
        template = random.choice(TRADE_REJECT)
        return template.format(name=self.name, program=program)

    def payment_sent(self, price: int) -> str:
        template = random.choice(PAYMENT_SENT)
        return template.format(name=self.name, price=price)

    def delivery_received(self, program: str = "") -> str:
        template = random.choice(DELIVERY_RECEIVED)
        return template.format(name=self.name, program=program)

    def price_adjust(self, program: str, old_price: int, new_price: int) -> str:
        template = random.choice(PRICE_ADJUST)
        return template.format(
            name=self.name, program=program, old_price=old_price, new_price=new_price
        )
