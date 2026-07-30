import asyncio

from elasticsearch import AsyncElasticsearch

from app.conf import app_config
from app.conf.app_config import ESConfig,app_config


class EsClientManager:
    def __init__(self, config:ESConfig):
        self.client: AsyncElasticsearch | None = None
        self.config: ESConfig = config

    def get_url(self):
        return f"http://{self.config.host}:{self.config.port}"

    def init(self):
        self.client = AsyncElasticsearch(
            hosts=[self.get_url()]
        )

    async def close(self):
        await self.client.close()


es_client_manager = EsClientManager(app_config.es)

if __name__ == '__main__':
    es_client_manager.init()
    client = es_client_manager.client

    async def test():
        # await client.indices.create(
        #     index = "books"
        # )
        #
        # await client.index(
        #     index = "books",
        #     document={
        #         "name": "Snow Crash",
        #         "author": "Neal Stephenson",
        #         "release": "1992-06-01",
        #         "page_count": 470
        #     },
        # )

        resp = await client.search(
            index = "books",
        )

        print(resp)

        await es_client_manager.close()


    asyncio.run(test())






