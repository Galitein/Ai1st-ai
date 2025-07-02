from src.database.sql import AsyncMySQLDatabase


db = AsyncMySQLDatabase()

async def get_trello_service_id():
    await db.create_pool()
    service_id = await db.select_one(table ="master_service", columns = "id", where= "service_name = 'Trello'")
    await db.close_pool()
    return service_id.get("id")


async def get_trello_token(ait_it:str):
    service_id = await get_trello_service_id()
    if not service_id:
        return None

    await db.create_pool()
    trello_token = await db.select_one(table="user_services",
                                        columns="auth_secret",
                                        where= f"service_id = {service_id} AND custom_gpt_id = '{ait_it}'"

    )
    await db.close_pool()
    return trello_token.get("auth_secret")

async def get_trello_api_key():
    await db.create_pool()
    service_name = "Trello"
    key = "api_key"

    trello_api_key = await db.select_one(
        table="master_settings",
        columns="value",
        where=f"service = '{service_name}' AND `key` = '{key}'"
    )
    await db.close_pool()
    return trello_api_key.get("value")
