import os
import sys
import asyncio
import logging
from typing import Optional
import aiohttp

logger = logging.getLogger("tg_bot")

class TelegramMiniAppBot:
    def __init__(self, token: str, webapp_url: str, pdf_path: str = ""):
        self.token = token
        url = (webapp_url or "").strip()
        if url and not (url.startswith("http://") or url.startswith("https://")):
            url = f"https://{url}"
        if url.startswith("http://") and not ("localhost" in url or "127.0.0.1" in url):
            url = "https://" + url[len("http://"):]
        self.webapp_url = url.rstrip("/")
        self.pdf_path = pdf_path
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.bot_info = None
        self._is_running = False

    async def _api_call(self, session: aiohttp.ClientSession, method: str, json_data: Optional[dict] = None) -> Optional[dict]:
        try:
            url = f"{self.api_url}/{method}"
            async with session.post(url, json=json_data, timeout=aiohttp.ClientTimeout(total=40)) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    logger.error(f"Telegram API error on {method}: {data.get('description')}")
                    return None
                return data.get("result")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error calling Telegram API {method}: {e}")
            return None

    async def setup_bot(self, session: aiohttp.ClientSession):
        """Verifies bot credentials and configures bot commands and menu button."""
        self.bot_info = await self._api_call(session, "getMe")
        if self.bot_info:
            logger.info(f"Connected to Telegram Bot: @{self.bot_info.get('username')} ({self.bot_info.get('first_name')})")

        # Configure Chat Menu Button to open Mini App directly
        if self.webapp_url.startswith("https://"):
            menu_button = {
                "menu_button": {
                    "type": "web_app",
                    "text": "📖 Китобни ўқиш",
                    "web_app": {
                        "url": self.webapp_url
                    }
                }
            }
            res = await self._api_call(session, "setChatMenuButton", menu_button)
            if res:
                logger.info(f"Configured Telegram Chat Menu Button -> {self.webapp_url}")

        # Set Bot Commands
        commands = {
            "commands": [
                {"command": "start", "description": "Китобхонни очиш / Запустить читалку"},
                {"command": "read", "description": "Мавлид китобини ўқиш / Читать"},
                {"command": "info", "description": "Китоб ҳақида маълумот / О книге"},
                {"command": "help", "description": "Фойдаланиш қўлланмаси / Помощь"}
            ]
        }
        await self._api_call(session, "setMyCommands", commands)

    async def send_welcome(self, session: aiohttp.ClientSession, chat_id: int):
        text = (
            "✨ <b>Ассаламу алайкум ва раҳматуллоҳи ва баракатуҳ!</b>\n\n"
            "📖 <b>«Мавлид ан-Набий»</b> электрон китобхонига хуш келибсиз.\n\n"
            "Муборак Мавлид китобини илова ичида қулай ва сифатли шаклда мутолаа қилишингиз мумкин:\n\n"
            "• 📄 <b>Саҳифама-саҳифа мутолаа</b> (24 саҳифали тўлиқ нусха)\n"
            "• 👆 <b>Осон бошқарув</b> — саҳифаларни суриш (swipe) ва четларини босиш орқали варақлаш\n"
            "• 🌙 <b>3 хил режим</b>: Кундузги (Light), Сепия (қоғоз), ва Тунги (Dark OLED)\n"
            "• 🔖 <b>Хатчўплар (Закладкалар)</b> — севимли салавот ва саҳифаларни сақлаб бориш\n"
            "• 📍 <b>Авто-эслаб қолиш</b> — ҳар сафар қолган саҳифангиздан давом этади\n\n"
            "<i>Мутолаани бошлаш учун қуйидаги тугмани босинг:</i>"
        )

        keyboard = [
            [
                {
                    "text": "📖 Китобни очиш (Mini App)",
                    "web_app": {"url": self.webapp_url}
                }
            ],
            [
                {"text": "ℹ️ Китоб ҳақида", "callback_data": "btn_info"},
                {"text": "❓ Қўлланма", "callback_data": "btn_help"}
            ]
        ]

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": keyboard
            }
        }
        await self._api_call(session, "sendMessage", payload)

    async def send_info(self, session: aiohttp.ClientSession, chat_id: int):
        text = (
            "📖 <b>«Мавлид ан-Набий» асари ҳақида</b>\n\n"
            "• <b>Номи:</b> Мавлид ан-Набий (Mawlid an-Nabiy)\n"
            "• <b>Ҳажми:</b> 24 саҳифа\n"
            "• <b>Мазмуни:</b> Пайғамбаримиз Муҳаммад Мустафо соллаллоҳу алайҳи васалламнинг таваллудлари, "
            "ҳаётлари, муборак сийратлари ва салавоту дуолар.\n"
            "• <b>Хусусиятлари:</b> Telegram Mini App, тунги режим, офлайн мутолаа, хатчўплар."
        )
        keyboard = [
            [{"text": "📖 Китобни очиш (Mini App)", "web_app": {"url": self.webapp_url}}]
        ]

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": keyboard}
        }
        await self._api_call(session, "sendMessage", payload)

    async def send_help(self, session: aiohttp.ClientSession, chat_id: int):
        text = (
            "💡 <b>Иловадан фойдаланиш бўйича қўлланма:</b>\n\n"
            "1️⃣ <b>Варақлаш:</b>\n"
            "   • Экранни чапга ёки ўнгга суринг (swipe).\n"
            "   • Ёки экраннинг ўнг чеккасини боссангиз кейингисига, чап чеккасини боссангиз олдингисига ўтади.\n\n"
            "2️⃣ <b>Меню ва созламалар:</b>\n"
            "   • Экраннинг ўртасини бир марта боссангиз, бошқарув панеллари очилади/ёпилади.\n\n"
            "3️⃣ <b>Тунги режим ва Сепия:</b>\n"
            "   • Юқоридаги созламалар тугмаси орқали кўзга қулай рангни (🌙 ёки 📜) танланг.\n\n"
            "4️⃣ <b>Хатчўп (Закладка):</b>\n"
            "   • Саҳифани эслаб қолиш учун юқоридаги 🔖 тугмасини босинг."
        )
        keyboard = [
            [{"text": "📖 Китобни очиш (Mini App)", "web_app": {"url": self.webapp_url}}]
        ]

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": keyboard}
        }
        await self._api_call(session, "sendMessage", payload)

    async def handle_callback_query(self, session: aiohttp.ClientSession, callback_query: dict):
        cq_id = callback_query.get("id")
        data = callback_query.get("data")
        message = callback_query.get("message", {})
        chat_id = message.get("chat", {}).get("id")

        await self._api_call(session, "answerCallbackQuery", {"callback_query_id": cq_id})

        if chat_id:
            if data == "btn_info":
                await self.send_info(session, chat_id)
            elif data == "btn_help":
                await self.send_help(session, chat_id)

    async def start_polling(self):
        """Asynchronous polling loop for Telegram updates."""
        self._is_running = True
        offset = 0
        logger.info("Telegram Bot polling started...")

        async with aiohttp.ClientSession() as session:
            await self.setup_bot(session)

            while self._is_running:
                try:
                    payload = {"offset": offset, "timeout": 20, "allowed_updates": ["message", "callback_query"]}
                    updates = await self._api_call(session, "getUpdates", payload)
                    if updates:
                        for u in updates:
                            update_id = u.get("update_id", 0)
                            offset = max(offset, update_id + 1)

                            if "message" in u:
                                msg = u["message"]
                                text = msg.get("text", "").strip()
                                chat_id = msg.get("chat", {}).get("id")

                                if not chat_id:
                                    continue

                                logger.info(f"Received message '{text}' from chat_id {chat_id}")

                                if text.startswith("/start") or text == "/read":
                                    await self.send_welcome(session, chat_id)
                                elif text.startswith("/info"):
                                    await self.send_info(session, chat_id)
                                elif text.startswith("/help"):
                                    await self.send_help(session, chat_id)
                                else:
                                    await self.send_welcome(session, chat_id)

                            elif "callback_query" in u:
                                await self.handle_callback_query(session, u["callback_query"])

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in Telegram polling loop: {e}")
                    await asyncio.sleep(2)

    def stop(self):
        self._is_running = False
