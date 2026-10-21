"""Talks to the MCP server over stdio exactly like Claude/Cursor would. Offline fixture, no keys."""
import anyio, json, os, sys, tempfile
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
async def main():
    p = StdioServerParameters(command=sys.executable, args=["-m", "ksmcp.server"], cwd=R,
        env={**os.environ, "PYTHONPATH": R, "KSMCP_FIXTURE": R + "/tests/fixture.json"})
    async with stdio_client(p) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        print("tools:", ", ".join(t.name for t in (await s.list_tools()).tools)); await anyio.sleep(1.5)
        print("\n> find_servers(api='github')")
        res = await s.call_tool("find_servers", {"api": "github", "limit": 3})
        for c in res.content:
            d = json.loads(c.text); print(f"  {d['grade']} {d['score']:>3}  {d['server']}")
        await anyio.sleep(1.5)
        print("\n> preview_config(api='github', clients_csv='cursor', top=1)   # writes nothing")
        d = json.loads((await s.call_tool("preview_config", {"api": "github", "clients_csv": "cursor", "top": 1, "sandbox_dir": tempfile.mkdtemp()})).content[0].text)
        print(json.dumps(d["results"][0]["config"], indent=1)[:600]); await anyio.sleep(3)
anyio.run(main)
