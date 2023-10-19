from os import getenv
import random, asyncio
from aptos_sdk.account import Account
from aptos_sdk.client import RestClient
from aptos_sdk.async_client import RestClient as RS
from concurrent.futures import ThreadPoolExecutor

NODE_URL = getenv("APTOS_NODE_URL", 'https://rpc.ankr.com/premium-http/aptos/730edb57ff917b8d398da10275b3d52de72e0637e2f73d949667d1eb9dc155b8/v1')
CANVAS_WIDTH = 999  # Canvas width
COLORS = {"blue": (500, 666, "0x02"), "yellow": (330, 500, "0x04")}  # Color data
PXL_NUM = random.randint(25, 90)  # Number of pixels

REST_CLIENT = RestClient(NODE_URL)  # Initialize REST Client
as_rest = RS(NODE_URL)  # Initialize Async REST Client
semaphore = asyncio.Semaphore(1)  # Async semaphore for limiting concurrency
executor = ThreadPoolExecutor()  # Thread pool for blocking calls

async def main():
    try:
        with open('pkey.txt', 'r') as f:  # Read private keys
            for line in f.readlines():
                private_key = line.strip()
                if not private_key: continue  # Skip empty lines
                acc = Account.load_key(private_key)  # Load Account using private key
                result = await process_profile(REST_CLIENT, acc, PXL_NUM)  # Process profile
                if result == 1: print(f"Success: {private_key}")
    except Exception as e:
        print(f"Unexpected error: {e}")

async def process_profile(RestClient, Account, num_pixels):
    balance = await get_account_balance_async(Account)  # Get account balance
    if balance is None: print("Error getting balance"); return 0  # Error case
    elif balance >= 1000000:  # Process transaction if balance is sufficient
        tx = await transfer_async(RestClient, Account, num_pixels)
        print(tx)
        try:
            RestClient.wait_for_transaction(tx)
        except AssertionError as e:
            print(f"AssertionError caught: {e}. Transaction may still be successful.")
        return 1
    elif balance < 1000000:  # Insufficient balance case
        print(f"Insufficient balance, fund account with coin. Address '{Account.address()}'...")
        return 0

async def get_account_balance_async(account):
    async with semaphore:  # Limit concurrency
        try:
            return int(await as_rest.account_balance(account_address=account.address()))
        except Exception as e:
            if "0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>" in str(e): print("Waiting for CoinStore to be available."); return 0  # Specific exception case
            else: print("An unexpected error occurred."); return None  # Unknown exception case

async def generate_block_color_payload(num_pixels):
    chosen_color = random.choice(["blue", "yellow"])  # Random color
    color_start, color_end, _ = COLORS[chosen_color]
    x, y = random.randint(0, CANVAS_WIDTH - 1), random.randint(color_start, color_end)  # Random start position
    x_coords, y_coords = [x], [y]  # Initialize coordinates
    for _ in range(1, num_pixels):
        x += random.randint(-20, 20); y += random.randint(-20, 20)  # Update coordinates
        x = min(max(x, 0), CANVAS_WIDTH - 1); y = min(max(y, color_start), color_end)  # Bound checks
        x_coords.append(x); y_coords.append(y)  # Append to list
    return chosen_color, x_coords, y_coords  # Return payload data


async def transfer_async(client, sender, num_pixels):
    chosen_color, x_coords, y_coords = await generate_block_color_payload(num_pixels)  # Generate payload
    print(f"X: {x_coords}, Y: {y_coords}")
    _, _, base_color_code = COLORS[chosen_color]
    payload_color = f"{base_color_code + (base_color_code[2:] * (num_pixels - 1))}"  # Generate color payload
    print(f"Payload Color: {payload_color}")

    first_payload = {
        "type": "entry_function_payload",
        "function": "0x915efe6647e0440f927d46e39bcb5eb040a7e567e1756e002073bc6e26f2cd23::canvas_token::draw",
        "type_arguments": [],
        "arguments": [
            "0x5d45bb2a6f391440ba10444c7734559bd5ef9053930e3ef53d05be332518522b",
            x_coords, y_coords, payload_color
        ],
    }

    first_result = await asyncio.get_event_loop().run_in_executor(executor,
                                                                  lambda: RestClient.submit_transaction(client, sender,
                                                                                                        first_payload))  # Submit first transaction

    if first_result:  # Check for success of first transaction
        second_payload = {
            "type": "entry_function_payload",
            "function": "0x3::token::opt_in_direct_transfer",
            "type_arguments": [],
            "arguments": [True]
        }

        second_result = await asyncio.get_event_loop().run_in_executor(executor,
                                                                       lambda: RestClient.submit_transaction(client,
                                                                                                             sender,
                                                                                                             second_payload))  # Submit second transaction
        return second_result

    return first_result
if __name__ == "__main__":
    asyncio.run(main())  # Run main function
