import asyncio, os
import asyncmy

HOST='rdbs-002-gen10-step3-2-oshima9.mysql.database.azure.com'
USER='tech0gen10student'  # ※ Single Server 形式が必要なら 'tech0gen10student@rdbs-002-gen10-step3-2-oshima9'
PASSWORD=os.getenv('MYSQL_PASSWORD') or '<<あなたのパスワード>>'
DB='serendigo_mock'

async def main():
    conn = await asyncmy.connect(
        host=HOST, user=USER, password=PASSWORD, db=DB,
        port=3306, ssl=True, charset='utf8mb4'
    )
    async with conn.cursor() as cur:
        await cur.execute("SELECT 1")
        print("SELECT 1 ->", await cur.fetchone())
    conn.close()

asyncio.run(main())
