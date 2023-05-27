from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from notion_client import Client
from datetime import datetime
from aiogram import types
from aiogram.dispatcher.middlewares import LifetimeControllerMiddleware
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import os
import re

# Define the regular expressions for validation
alphanumeric_regex = re.compile(r'^[a-zA-Z0-9\s]+$')
numeric_regex = re.compile(r'^\d+(\.\d+)?$')

# Predefined list of categories
categories = ['Food', 'Transport', 'Entertainment', 'Rent', 'Internet', 'Education', 'Utilities', 'Other']


def add_cancel_button():
    def decorator(func):
        async def wrapper(message: types.Message, state: FSMContext = None, **kwargs):
            # Create a keyboard without a cancel button
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)

            if state is not None:
                # Load the current state data
                async with state.proxy() as data:
                    kwargs['data'] = data

                    # Check if the cancel flag is set
                    if data.get('cancel', False):
                        # Add the cancel button to the keyboard
                        keyboard.add(KeyboardButton('/cancel'))

                # Call the function with the state and keyboard
                await func(message, state, keyboard, **kwargs)
            else:
                # Call the function with the keyboard
                await func(message, keyboard, **kwargs)

        return wrapper

    return decorator


# Initialize the bot and dispatcher
bot = Bot(token=os.getenv("TELEGRAM_API_TOKEN"))
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LifetimeControllerMiddleware())

# Initialize the Notion client and table ID
notion = Client(auth=os.getenv("NOTION_API_KEY"))
table_id = os.getenv("NOTION_TABLE_ID")
tg_admin_id = os.getenv("TELEGRAM_ADMIN_ID")


# Define the state machine for adding an expense
class AddExpense(StatesGroup):
    name = State()
    amount = State()
    date = State()
    category = State()
    comment = State()


class EditLastExpense(StatesGroup):
    name = State()
    amount = State()
    date = State()
    category = State()
    comment = State()


async def on_startup(dp):
    result = notion.databases.query(
        database_id=table_id,
        sorts=[{"property": "Date", "direction": "descending"}],
        page_size=1
    )

    # Create a keyboard with buttons for the /help and /add_expense commands
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('/help'), KeyboardButton('/add_expense'))

    if len(result["results"]) > 0:
        # If the table is not empty, add the /edit_last_expense command
        keyboard.add(KeyboardButton('/edit_last_expense'))

    # Send a message with the available commands
    await bot.send_message(chat_id=tg_admin_id, text="Welcome to the Notion Expense Tracker bot!\n\n"
                                                     "Here are the available commands:", reply_markup=keyboard)
    await bot.send_message(chat_id=tg_admin_id, text="/help - Show this help message")
    await bot.send_message(chat_id=tg_admin_id, text="/add_expense - Add a new expense")
    if len(result["results"]) > 0:
        await bot.send_message(chat_id=tg_admin_id, text="/edit_last_expense - Edit last expense")


async def on_shutdown():
    await bot.send_message(chat_id=tg_admin_id, text="Bot stopped")
    notion.close()


# Define the command handlers for the bot
@add_cancel_button()
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    # Create a keyboard with buttons for the /help and /add_expense commands
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton('/help'), KeyboardButton('/add_expense'))

    # Send a message with the keyboard
    await message.answer("Welcome to the Notion Expense Tracker bot!", reply_markup=keyboard)


@dp.message_handler(commands=["help"])
async def help(message: types.Message):
    # Create a keyboard with a button for the /add_expense command
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('/add_expense'))

    help_message = "Here are the available commands:\n"
    help_message += "/help - Show this help message\n"
    help_message += "/add_expense - Add a new expense\n"
    await message.answer(help_message, reply_markup=keyboard)


@dp.message_handler(commands=["cancel"], state="*")
async def cancel_handler(message: types.Message, state: FSMContext):
    # Clear the cancel flag in the state
    async with state.proxy() as data:
        data['cancel'] = False

    await state.finish()
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)

    # Query the last entry in the database to check if it's empty
    result = notion.databases.query(
        database_id=table_id,
        sorts=[{"property": "Date", "direction": "descending"}],
        page_size=1
    )

    keyboard.add(KeyboardButton('/help'), KeyboardButton('/add_expense'))
    if len(result["results"]) > 0:  # Add /edit_last_expense if the table is not empty
        keyboard.add(KeyboardButton('/edit_last_expense'))

    await message.answer("Command cancelled.", reply_markup=keyboard)


@add_cancel_button()
@dp.message_handler(commands=["add_expense"])
async def add_expense(message: types.Message, state: FSMContext):
    # Set the cancel flag in the state
    async with state.proxy() as data:
        data['cancel'] = True

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('/cancel'))

    await message.answer("What's the name of the expense?", reply_markup=keyboard)
    await AddExpense.name.set()


@add_cancel_button()
@dp.message_handler(state=AddExpense.name)
async def add_expense_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not alphanumeric_regex.match(name):
        await message.answer("Invalid input. Name should only contain alphanumeric characters and spaces.")
        return

    async with state.proxy() as data:
        data['name'] = message.text

    await message.answer("How much was the expense?")
    await AddExpense.amount.set()


@add_cancel_button()
@dp.message_handler(state=AddExpense.amount)
async def add_expense_amount(message: types.Message, state: FSMContext):
    amount = message.text.strip()
    if not numeric_regex.match(amount):
        await message.answer("Invalid input. Amount should be a number.")
        return

    async with state.proxy() as data:
        data['amount'] = message.text

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    for category in categories:
        keyboard.add(KeyboardButton(category))

    await message.answer("Select a category for this expense:", reply_markup=keyboard)
    await AddExpense.category.set()


@add_cancel_button()
@dp.message_handler(state=AddExpense.date)
async def add_expense_date(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        try:
            date = datetime.strptime(message.text, "%Y-%m-%d")
            data['date'] = date.date().isoformat()
        except ValueError:
            await message.answer("Invalid date format. Please enter a date in the format YYYY-MM-DD.")
            return

    await message.answer("What category does the expense belong to?")
    await AddExpense.category.set()


@add_cancel_button()
@dp.message_handler(state=AddExpense.category)
async def add_expense_category(message: types.Message, state: FSMContext):
    category = message.text.strip()
    if category not in categories:
        await message.answer("Invalid category. Please select one of the available categories.")
        return

    async with state.proxy() as data:
        data['category'] = message.text
        data['date'] = datetime.now().date().isoformat()

    # Save the data to the Notion table
    notion_expense = {
        "Name": {"title": [{"text": {"content": data['name']}}]},
        "Amount": {"number": float(data['amount'])},
        "Date": {"date": {"start": data['date']}},
        "Category": {"rich_text": [{"text": {"content": data['category']}}]},
        "Comment": {"rich_text": [{"text": {"content": ""}}]}  # Comment is left blank for now
    }
    notion.pages.create(parent={"database_id": table_id}, properties=notion_expense)

    # Reset the state machine
    await state.finish()

    # Reset the keyboard markup to include the edit_last_expense command
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('/help'), KeyboardButton('/add_expense'), KeyboardButton('/edit_last_expense'))
    await message.answer("Expense added successfully!", reply_markup=keyboard)


@add_cancel_button()
@dp.message_handler(commands=["edit_last_expense"], state="*")
async def edit_last_expense(message: types.Message, state: FSMContext):
    # Fetch the last expense from the Notion table
    result = notion.databases.query(
        database_id=table_id,
        sorts=[{"property": "Date", "direction": "descending"}],
        page_size=1
    )

    if len(result["results"]) == 0:
        await message.answer("No expenses found to edit.")
        return

    last_expense = result["results"][0]
    last_expense_id = last_expense["id"]

    async with state.proxy() as data:
        data['last_expense_id'] = last_expense_id

        # Retrieve the current column values of the last expense
        name = last_expense["properties"]["Name"]["title"][0]["plain_text"]
        amount = str(last_expense["properties"]["Amount"]["number"])
        date = last_expense["properties"]["Date"]["date"]["start"]
        category = last_expense["properties"]["Category"]["rich_text"][0]["plain_text"]

        # Check if Comment exists and if it's not empty
        if "Comment" in last_expense["properties"] and last_expense["properties"]["Comment"]["rich_text"]:
            comment = last_expense["properties"]["Comment"]["rich_text"][0]["plain_text"]
        else:
            comment = ''

        data['name'] = name
        data['amount'] = amount
        data['date'] = date
        data['category'] = category
        data['comment'] = comment

    # Include comment in the message if it exists
    message_text = "Current column values of the last expense:\n" \
                   f"Name: {name}\n" \
                   f"Amount: {amount}\n" \
                   f"Date: {date}\n" \
                   f"Category: {category}"
    if comment:
        message_text += f"\nComment: {comment}"

    await message.answer(message_text)

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('/cancel'))

    await message.answer("Enter the new value for the 'Name' column:", reply_markup=keyboard)
    await EditLastExpense.name.set()


@add_cancel_button()
@dp.message_handler(state=EditLastExpense.name)
async def edit_expense_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not alphanumeric_regex.match(name):
        await message.answer("Invalid input. Name should only contain alphanumeric characters and spaces.")
        return

    async with state.proxy() as data:
        data['name'] = message.text

    await message.answer("Enter the new value for the 'Amount' column:")
    await EditLastExpense.amount.set()


@add_cancel_button()
@dp.message_handler(state=EditLastExpense.amount)
async def edit_expense_amount(message: types.Message, state: FSMContext):
    amount = message.text.strip()
    if not numeric_regex.match(amount):
        await message.answer("Invalid input. Amount should be a number.")
        return

    async with state.proxy() as data:
        data['amount'] = message.text

    await message.answer("Enter the new comment for the expense:")
    await EditLastExpense.comment.set()


@add_cancel_button()
@dp.message_handler(state=EditLastExpense.comment)
async def edit_expense_comment(message: types.Message, state: FSMContext):
    comment = message.text.strip()
    async with state.proxy() as data:
        data['comment'] = comment

    await message.answer("Enter the new value for the 'Date' column (YYYY-MM-DD):")
    await EditLastExpense.date.set()


@add_cancel_button()
@dp.message_handler(state=EditLastExpense.date)
async def edit_expense_date(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        try:
            date = datetime.strptime(message.text, "%Y-%m-%d")
            data['date'] = date.date().isoformat()
        except ValueError:
            await message.answer("Invalid date format. Please enter a date in the format YYYY-MM-DD.")
            return

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    for category in categories:
        keyboard.add(KeyboardButton(category))

    await message.answer("Enter the new value for the 'Category' column:", reply_markup=keyboard)
    await EditLastExpense.category.set()


@add_cancel_button()
@dp.message_handler(state=EditLastExpense.category)
async def edit_expense_category(message: types.Message, state: FSMContext):
    category = message.text.strip()
    if category not in categories:
        await message.answer("Invalid category. Please select one of the available categories.")
        return

    async with state.proxy() as data:
        data['category'] = message.text

        # Retrieve the current column values from the state
        last_expense_id = data['last_expense_id']
        name = data['name']
        amount = float(data['amount'])
        date = data['date']
        comment = data['comment']

        # Update the last expense record in the Notion table
    notion_expense = {
        "Name": {"title": [{"text": {"content": name}}]},
        "Amount": {"number": amount},
        "Date": {"date": {"start": date}},
        "Category": {"rich_text": [{"text": {"content": category}}]},
        "Comment": {"rich_text": [{"text": {"content": comment}}]}
    }
    notion.pages.update(page_id=last_expense_id, properties=notion_expense)

    # Reset the state machine
    await state.finish()

    # Reset the keyboard markup to include the edit_last_expense command
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('/help'), KeyboardButton('/add_expense'), KeyboardButton('/edit_last_expense'))
    await message.answer("Expense updated successfully!", reply_markup=keyboard)


dp.register_message_handler(start, commands=["start"])
dp.register_message_handler(help, commands=["help"])
dp.register_message_handler(add_expense, commands=["add_expense"])
dp.register_message_handler(add_expense_name, state=AddExpense.name)
dp.register_message_handler(add_expense_amount, state=AddExpense.amount)
dp.register_message_handler(add_expense_date, state=AddExpense.date)
dp.register_message_handler(add_expense_category, state=AddExpense.category)
dp.register_message_handler(edit_last_expense, commands=["edit_last_expense"])
dp.register_message_handler(edit_expense_name, state=EditLastExpense.name)
dp.register_message_handler(edit_expense_amount, state=EditLastExpense.amount)
dp.register_message_handler(edit_expense_date, state=EditLastExpense.date)
dp.register_message_handler(edit_expense_category, state=EditLastExpense.category)
dp.register_message_handler(edit_expense_comment, state=EditLastExpense.comment)

if __name__ == '__main__':
    from aiogram import executor

    # Start the bot
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown)
