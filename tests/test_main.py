from aiohttp import web

from algobot import __main__ as main


async def test_ping(aiohttp_client):
    app = web.Application()
    app.router.add_post("/webhook", main.main)
    client = await aiohttp_client(app)
    headers = {"X-GitHub-Event": "ping", "X-GitHub-Delivery": "1234"}
    data = {"zen": "testing is good"}
    response = await client.post("/webhook", headers=headers, json=data)
    assert response.status == 200


async def test_failure(aiohttp_client):
    """Even in the face of an exception, the server should not crash."""
    app = web.Application()
    app.router.add_post("/webhook", main.main)
    client = await aiohttp_client(app)
    # Missing key headers.
    response = await client.post("/webhook", headers={})
    assert response.status == 500


async def test_success(aiohttp_client):
    app = web.Application()
    app.router.add_post("/webhook", main.main)
    client = await aiohttp_client(app)
    headers = {"X-GitHub-Event": "project", "X-GitHub-Delivery": "1234"}
    # Sending a payload that shouldn't trigger any networking, but no errors
    # either.
    data = {"action": "created"}
    response = await client.post("/webhook", headers=headers, json=data)
    assert response.status == 200
