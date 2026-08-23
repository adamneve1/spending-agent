import asyncio
import os
from datetime import date, datetime

from dotenv import load_dotenv
from google import genai
from google.genai import types

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)


load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY tidak ditemukan")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN tidak ditemukan")


gemini = genai.Client(api_key=GEMINI_API_KEY)

TODAY = date.today().strftime("%d %b %Y")


# ============================================================
# MCP → GEMINI TOOL
# ============================================================

def mcp_tools_to_gemini(mcp_tools):
    declarations = []

    for tool in mcp_tools:
        declarations.append(
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description or "",
                parameters=tool.input_schema,
            )
        )

    return types.Tool(function_declarations=declarations)


# ============================================================
# DATE NORMALIZATION
# ============================================================

def normalize_expense_date(value):
    today = date.today()

    if not value:
        return today.strftime("%d %b %Y")

    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()

        if abs((parsed - today).days) > 365:
            return today.strftime("%d %b %Y")

        return parsed.strftime("%d %b %Y")

    except ValueError:
        pass

    try:
        parsed = datetime.strptime(value, "%d %b %Y").date()
        return parsed.strftime("%d %b %Y")

    except ValueError:
        return today.strftime("%d %b %Y")


# ============================================================
# ALLOWED CATEGORIES
# ============================================================

ALLOWED_CATEGORIES = {
    "Service Motor",
    "BPJS",
    "Food",
    "Self Care",
    "Bensin",
    "Cicilan Emas",
    "Debt CC",
    "Food Debt CC",
    "Sedekah",
}


# ============================================================
# GEMINI SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = f"""
You are a personal spending assistant.

Today's date is {TODAY}.

When the user tells you about an expense,
use the available add_expense tool.

Extract:

- date
- description
- category
- amount

Date rules:

- "hari ini" = today's date
- "tadi" = today's date
- "kemarin" = yesterday's date
- If the user explicitly gives a date, use that date.
- If no date is provided, use today's date.
- NEVER invent a date.
- NEVER use an old arbitrary date.

Allowed expense categories:

Needs:

- Service Motor
- BPJS
- Food
- Self Care
- Bensin
- Cicilan Emas
- Debt CC
- Food Debt CC
- Sedekah

Category rules:

- You MUST choose exactly one category from the Needs list.
- NEVER create a new category.
- NEVER modify category names.

Use:

- Food → food or eating
- Bensin → fuel, gasoline, BBM, Pertalite, Pertamax, solar
- Service Motor → motorcycle service or repair
- BPJS → BPJS payment
- Self Care → personal care
- Cicilan Emas → gold installment
- Debt CC → credit card debt
- Food Debt CC → food expense specifically related to credit card debt
- Sedekah → donation or giving


If you cannot confidently determine the category,
ASK the user for clarification.

Do not invent an amount.

After successfully adding the expense,
tell the user briefly that it was recorded.
"""


# ============================================================
# GLOBAL MCP + GEMINI SESSION
# ============================================================

mcp_session = None
chat = None


# ============================================================
# TELEGRAM MESSAGE HANDLER
# ============================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global mcp_session
    global chat

    if not update.message:
        return

    user_input = update.message.text

    if not user_input:
        return

    print(f"\n[Telegram] {user_input}")

    try:

        # ----------------------------------------------------
        # Gemini
        # ----------------------------------------------------

        response = await asyncio.to_thread(
            chat.send_message,
            user_input
        )

        # ----------------------------------------------------
        # Gemini meminta MCP tool
        # ----------------------------------------------------

        if response.function_calls:

            for function_call in response.function_calls:

                print(
                    f"\n[AI → MCP] {function_call.name}"
                )

                arguments = dict(function_call.args)

                # --------------------------------------------
                # ADD EXPENSE
                # --------------------------------------------

                if function_call.name == "add_expense":

                    arguments["date"] = normalize_expense_date(
                        arguments.get("date")
                    )

                    category = arguments.get("category")

                    # ----------------------------------------
                    # Hard validation
                    # ----------------------------------------

                    if category not in ALLOWED_CATEGORIES:

                        description = arguments.get(
                            "description",
                            ""
                        ).lower()

                        # Gemini kadang masih mencoba
                        # Transportation untuk bensin.
                        if category in {
                            "Transportation",
                            "Transport",
                            "Fuel",
                            "Gas",
                            "Gasoline",
                        }:

                            fuel_keywords = [
                                "bensin",
                                "bbm",
                                "pertalite",
                                "pertamax",
                                "solar",
                                "isi bensin",
                                "isi bbm",
                                "fuel",
                            ]

                            if any(
                                keyword in description
                                for keyword in fuel_keywords
                            ):
                                arguments["category"] = "Bensin"

                            else:
                                await update.message.reply_text(
                                    "Kategori transaksi ini nggak jelas. "
                                    "Mau masuk kategori apa?"
                                )
                                return

                        else:

                            await update.message.reply_text(
                                "Kategori transaksi ini nggak jelas. "
                                "Coba jelaskan pengeluarannya."
                            )
                            return

                print(
                    f"Arguments: {arguments}"
                )

                # --------------------------------------------
                # MCP
                # --------------------------------------------

                result = await mcp_session.call_tool(
                    function_call.name,
                    arguments=arguments,
                )

                # --------------------------------------------
                # MCP → Gemini
                # --------------------------------------------

                response = await asyncio.to_thread(
                    chat.send_message,
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=function_call.name,
                            response={
                                "result":
                                    result.structured_content
                                    if result.structured_content
                                    else str(result.content)
                            },
                        )
                    )
                )

        # ----------------------------------------------------
        # Kirim jawaban ke Telegram
        # ----------------------------------------------------

        await update.message.reply_text(
            response.text
        )

    except Exception as e:

        print(f"[ERROR] {repr(e)}")

        await update.message.reply_text(
            "Ada error waktu proses transaksi. "
            "Cek terminal server."
        )


# ============================================================
# START
# ============================================================

async def main():

    global mcp_session
    global chat

    # --------------------------------------------------------
    # MCP SERVER
    # --------------------------------------------------------

    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
    )

    async with stdio_client(
        server_params
    ) as (read_stream, write_stream):

        async with ClientSession(
            read_stream,
            write_stream
        ) as session:

            mcp_session = session

            # ------------------------------------------------
            # Initialize MCP
            # ------------------------------------------------

            await session.initialize()

            tools_result = await session.list_tools()

            print("\nMCP tools:")

            for tool in tools_result.tools:
                print(
                    f"- {tool.name}: {tool.description}"
                )

            gemini_tool = mcp_tools_to_gemini(
                tools_result.tools
            )

            # ------------------------------------------------
            # Gemini Chat
            # ------------------------------------------------

            chat = gemini.chats.create(
                model="gemini-3.1-flash-lite",
                config=types.GenerateContentConfig(
                    tools=[gemini_tool],
                    system_instruction=SYSTEM_PROMPT,
                ),
            )

            print("\nSpending Agent Telegram siap.")

            # ------------------------------------------------
            # Telegram
            # ------------------------------------------------

            app = (
                ApplicationBuilder()
                .token(TELEGRAM_BOT_TOKEN)
                .build()
            )

            app.add_handler(
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_message,
                )
            )

            print("Bot Telegram running...")

            await app.initialize()
            await app.start()
            await app.updater.start_polling()

            try:

                # Keep application alive
                while True:
                    await asyncio.sleep(3600)

            finally:

                await app.updater.stop()
                await app.stop()
                await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())