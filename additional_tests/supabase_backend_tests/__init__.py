#  This file is part of OctoBot (https://github.com/Drakkar-Software/OctoBot)
#  Copyright (c) 2023 Drakkar-Software, All rights reserved.
#
#  OctoBot is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either
#  version 3.0 of the License, or (at your option) any later version.
#
#  OctoBot is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public
#  License along with OctoBot. If not, see <https://www.gnu.org/licenses/>.
import contextlib
import os
import dotenv
import pytest_asyncio

import octobot.community as community
import octobot.community.supabase_backend.enums as supabase_backend_enums
import octobot_commons.configuration as commons_configuration


LOADED_BACKEND_CREDS_ENV_VARIABLES = False


@pytest_asyncio.fixture
async def authenticated_client_1():
    async with _authenticated_client(*_get_backend_client_creds(1)) as client:
        yield client


@pytest_asyncio.fixture
async def authenticated_client_1_with_temp_bot():
    async with _authenticated_client(*_get_backend_client_creds(1)) as client:
        bot_id = None
        try:
            bot = await client.create_bot()
            bot_id = bot[supabase_backend_enums.BotKeys.ID.value]
            yield client, bot_id
        finally:
            if bot_id is not None:
                await _delete_bot(client, bot_id)


@pytest_asyncio.fixture
async def authenticated_client_2():
    async with _authenticated_client(*_get_backend_client_creds(2)) as client:
        yield client


async def _delete_bot(client, bot_id):

    async def _delete_portfolio_histories(portfolio_id):
        await client.table("bot_portfolio_histories").delete().eq(
            supabase_backend_enums.PortfolioHistoryKeys.PORTFOLIO_ID.value, portfolio_id
        ).execute()

    async def _delete_portfolio(portfolio_id):
        await client.table("bot_portfolios").delete().eq(
            supabase_backend_enums.PortfolioKeys.ID.value, portfolio_id
        ).execute()

    async def _delete_config(config_id):
        await client.table("bot_configs").delete().eq(
            supabase_backend_enums.ConfigKeys.ID.value, config_id
        ).execute()
    # cleanup trades
    await client.reset_trades(bot_id)
    portfolios = await client.fetch_portfolios(bot_id)
    if portfolios:
        # cleanup portfolios
        # remove portfolio foreign key
        await client.update_bot(
            bot_id,
            {supabase_backend_enums.BotKeys.CURRENT_PORTFOLIO_ID.value: None}
        )
        for portfolio in portfolios:
            to_del_portfolio_id = portfolio[supabase_backend_enums.PortfolioKeys.ID.value]
            await _delete_portfolio_histories(to_del_portfolio_id)
            await _delete_portfolio(to_del_portfolio_id)
    configs = await client.fetch_configs(bot_id)
    if configs:
        # cleanup configs
        # remove configs foreign key
        await client.update_bot(
            bot_id,
            {supabase_backend_enums.BotKeys.CURRENT_CONFIG_ID.value: None}
        )
        for config in configs:
            to_del_config_id = config[supabase_backend_enums.ConfigKeys.ID.value]
            await _delete_config(to_del_config_id)
    # delete bot
    deleted_bot = (await client.delete_bot(bot_id))[0]
    assert deleted_bot[supabase_backend_enums.BotKeys.ID.value] == bot_id


@contextlib.asynccontextmanager
async def _authenticated_client(email, password):
    config = commons_configuration.Configuration("", "")
    config.config = {}
    backend_url, backend_key = _get_backend_api_creds()
    supabase_client = None
    try:
        supabase_client = community.CommunitySupabaseClient(
            backend_url,
            backend_key,
            community.SyncConfigurationStorage(config)
        )
        supabase_client.sign_in(email, password)
        yield supabase_client
    finally:
        if supabase_client:
            supabase_client.close()


def _load_backend_creds_env_variables_if_necessary():
    global LOADED_BACKEND_CREDS_ENV_VARIABLES
    if not LOADED_BACKEND_CREDS_ENV_VARIABLES:
        # load environment variables from .env file if exists
        dotenv_path = os.getenv("SUPABASE_BACKEND_TESTS_DOTENV_PATH", os.path.dirname(os.path.abspath(__file__)))
        dotenv.load_dotenv(os.path.join(dotenv_path, ".env"), verbose=False)
        LOADED_BACKEND_CREDS_ENV_VARIABLES = True


def _get_backend_api_creds():
    return os.getenv("SUPABASE_BACKEND_URL"), os.getenv("SUPABASE_BACKEND_KEY")


def _get_backend_client_creds(identifier):
    return os.getenv(f"SUPABASE_BACKEND_CLIENT_{identifier}_EMAIL"), \
        os.getenv(f"SUPABASE_BACKEND_CLIENT_{identifier}_PASSWORD")


_load_backend_creds_env_variables_if_necessary()
