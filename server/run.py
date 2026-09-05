from alpha_poker_api.main import app

if __name__ == "__main__":
    import uvicorn

    # Training WebSocket URLs contain short-lived capability tokens. Keep raw
    # request targets out of local logs while retaining startup and error logs.
    uvicorn.run(app, host="127.0.0.1", port=8000, access_log=False)
