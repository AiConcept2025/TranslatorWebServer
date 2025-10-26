#!/usr/bin/env python3
"""
optimize_db.py - MongoDB query optimization and index management
Handles complex DB optimization logic outside of Claude to save tokens
"""

import asyncio
import argparse
import json
from typing import Dict, List
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pathlib import Path

class MongoOptimizer:
    """Optimize MongoDB queries and indexes."""
    
    def __init__(self, uri: str = "mongodb://localhost:27017", db_name: str = "translation"):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]
    
    async def run_optimization(self, collection_name: str = None):
        """Run full optimization workflow."""
        print("🔍 Starting MongoDB Optimization\n")
        
        await self.enable_profiling()
        slow_queries = await self.find_slow_queries(collection_name)
        recommendations = self.analyze_queries(slow_queries)
        
        if recommendations:
            await self.create_indexes(recommendations)
        
        await self.verify_improvements()
        self.generate_report(slow_queries, recommendations)
    
    async def enable_profiling(self, level: int = 1, slow_ms: int = 100):
        """Enable query profiling for slow queries."""
        try:
            await self.db.command("profile", level, slowms=slow_ms)
            print(f"✅ Profiling enabled (level={level}, slow_ms={slow_ms})")
        except Exception as e:
            print(f"⚠️  Profiling already enabled or error: {e}")
    
    async def find_slow_queries(self, collection: str = None) -> List[Dict]:
        """Find slow queries from system profile."""
        query = {"millis": {"$gt": 100}}
        if collection:
            query["ns"] = f"{self.db.name}.{collection}"
        
        profile_collection = self.db.system.profile
        slow_queries = await profile_collection.find(query).sort("millis", -1).limit(20).to_list(None)
        
        print(f"📊 Found {len(slow_queries)} slow queries\n")
        
        results = []
        for query in slow_queries[:5]:
            result = {
                'collection': query.get('ns', '').split('.')[-1],
                'operation': query.get('op'),
                'duration_ms': query.get('millis'),
                'timestamp': query.get('ts'),
                'filter': query.get('command', {}).get('filter', {}),
                'sort': query.get('command', {}).get('sort', {})
            }
            results.append(result)
            
            print(f"  ⏱️  {result['collection']}.{result['operation']} - {result['duration_ms']}ms")
            if result['filter']:
                print(f"     Filter: {self._format_filter(result['filter'])}")
        
        return results
    
    def analyze_queries(self, queries: List[Dict]) -> List[Dict]:
        """Generate index recommendations from slow queries."""
        recommendations = []
        seen_indexes = set()
        
        for query in queries:
            if not query['filter'] and not query['sort']:
                continue
            
            index_fields = []
            
            for field in query['filter'].keys():
                if field not in ['$or', '$and', '$nor']:
                    index_fields.append((field, 1))
            
            for field, direction in query['sort'].items():
                if (field, direction) not in index_fields:
                    index_fields.append((field, direction))
            
            if index_fields:
                index_key = str(index_fields)
                if index_key not in seen_indexes:
                    seen_indexes.add(index_key)
                    recommendations.append({
                        'collection': query['collection'],
                        'index': index_fields,
                        'reason': f"Optimize {query['operation']} ({query['duration_ms']}ms)"
                    })
        
        print(f"\n📋 Generated {len(recommendations)} index recommendations\n")
        for rec in recommendations:
            print(f"  💡 {rec['collection']}: {rec['index']}")
        
        return recommendations
    
    async def create_indexes(self, recommendations: List[Dict]):
        """Create recommended indexes."""
        print("\n🔨 Creating indexes...\n")
        
        for rec in recommendations:
            collection = self.db[rec['collection']]
            
            existing = await collection.list_indexes().to_list(None)
            index_exists = any(
                self._same_index(idx.get('key', {}), dict(rec['index']))
                for idx in existing
            )
            
            if not index_exists:
                try:
                    index_name = await collection.create_index(rec['index'])
                    print(f"  ✅ Created index '{index_name}' on {rec['collection']}")
                except Exception as e:
                    print(f"  ❌ Failed to create index on {rec['collection']}: {e}")
            else:
                print(f"  ⏭️  Index already exists on {rec['collection']}")
    
    async def verify_improvements(self):
        """Run explain on common queries to verify improvements."""
        print("\n🔬 Verifying improvements...\n")
        
        collection = self.db.translations
        cursor = collection.find({"user_id": "test", "status": "completed"})
        explain = await cursor.explain()
        
        execution_stats = explain.get('executionStats', {})
        
        print(f"  📈 Query Performance:")
        print(f"     Execution Time: {execution_stats.get('executionTimeMillis', 'N/A')}ms")
        print(f"     Documents Examined: {execution_stats.get('totalDocsExamined', 'N/A')}")
    
    def generate_report(self, queries: List[Dict], recommendations: List[Dict]):
        """Generate optimization report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'slow_queries_found': len(queries),
            'indexes_recommended': len(recommendations),
            'top_slow_queries': queries[:5],
            'recommendations': recommendations
        }
        
        report_file = f"reports/db_optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        Path("reports").mkdir(exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n📄 Report saved: {report_file}")
    
    def _format_filter(self, filter_dict: Dict) -> str:
        """Format filter for display."""
        return ', '.join(f"{k}={v}" for k, v in filter_dict.items())
    
    def _same_index(self, idx1: Dict, idx2: Dict) -> bool:
        """Check if two indexes are the same."""
        return list(idx1.items()) == list(idx2.items())
    
    async def cleanup(self):
        """Close MongoDB connection."""
        self.client.close()

async def main():
    parser = argparse.ArgumentParser(description='MongoDB Optimization Tool')
    parser.add_argument('--collection', help='Specific collection to optimize')
    parser.add_argument('--uri', default='mongodb://localhost:27017', help='MongoDB URI')
    parser.add_argument('--db', default='translation', help='Database name')
    
    args = parser.parse_args()
    
    optimizer = MongoOptimizer(args.uri, args.db)
    
    try:
        await optimizer.run_optimization(args.collection)
    finally:
        await optimizer.cleanup()

if __name__ == "__main__":
    asyncio.run(main())

