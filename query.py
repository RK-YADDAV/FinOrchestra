import asyncio
from dotenv import load_dotenv
import os
from sqlalchemy import text
from db.session import get_isolated_engine
import json

load_dotenv()

async def main():
    engine = get_isolated_engine()
    async with engine.connect() as conn:
        try:
            result = await conn.execute(text("SELECT run_id, AVG(composite_score) as avg_score, count(*) as count FROM eval_results GROUP BY run_id ORDER BY avg_score DESC LIMIT 5"))
            rows = result.fetchall()
            if not rows:
                print("No evaluation runs found in the database. Run the evaluation harness first.")
                return
            
            print("Latest/Best Evaluation Runs:")
            for row in rows:
                print(f"Run ID: {row.run_id}, Avg Composite Score: {row.avg_score}, Total Cases: {row.count}")
                
            latest_run = rows[0].run_id
            print(f"\nDetails for Run ID: {latest_run}")
            details = await conn.execute(text("SELECT test_case_id, category, composite_score, math_accuracy, citation_accuracy, premise_rejection, tool_efficiency FROM eval_results WHERE run_id = :run_id"), {"run_id": latest_run})
            
            for d in details.fetchall():
                print(f"[{d.test_case_id}] {d.category} - Composite: {d.composite_score} (Math: {d.math_accuracy}, Cite: {d.citation_accuracy}, Premise: {d.premise_rejection}, Tool: {d.tool_efficiency})")
        except Exception as e:
            print(f"Error querying database: {e}")
            print("It's possible the eval_results table hasn't been created yet.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
