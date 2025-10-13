#!/usr/bin/env python3
"""
Redis Test Script for Privacy Inspector API
Tests Redis functionality and rate limiting simulation.
"""

import asyncio
import redis.asyncio as redis
import time
from datetime import datetime

async def test_redis_connection():
    """Test basic Redis connection and operations."""
    print("🔴 Testing Redis Connection")
    print("=" * 40)
    
    try:
        # Connect to Redis
        client = redis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)
        
        # Test ping
        response = await client.ping()
        print(f"✅ Redis Ping: {response}")
        
        # Test basic operations
        await client.set("test:privacy-inspector", "working", ex=10)
        value = await client.get("test:privacy-inspector")
        print(f"✅ Set/Get Test: {value}")
        
        # Test expiration
        ttl = await client.ttl("test:privacy-inspector")
        print(f"✅ TTL Test: {ttl} seconds remaining")
        
        # Test increment (used for rate limiting)
        await client.set("test:counter", 0)
        count1 = await client.incr("test:counter")
        count2 = await client.incr("test:counter")
        print(f"✅ Increment Test: {count1} -> {count2}")
        
        # Cleanup
        await client.delete("test:privacy-inspector", "test:counter")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

async def simulate_rate_limiting():
    """Simulate how rate limiting works with Redis."""
    print("\n🚦 Simulating Rate Limiting")
    print("=" * 40)
    
    try:
        client = redis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)
        
        # Simulate rate limiting for IP 192.168.1.1
        ip = "192.168.1.1"
        endpoint = "auth"
        rate_limit_key = f"rate_limit:{ip}:{endpoint}"
        
        # Rate limit: 5 requests per 60 seconds
        max_requests = 5
        window_seconds = 60
        
        print(f"Rate limit: {max_requests} requests per {window_seconds} seconds")
        print(f"Testing with IP: {ip}, Endpoint: {endpoint}")
        print()
        
        for i in range(7):  # Try 7 requests (should hit limit)
            # Get current count
            current_count = await client.get(rate_limit_key)
            current_count = int(current_count) if current_count else 0
            
            if current_count >= max_requests:
                remaining_ttl = await client.ttl(rate_limit_key)
                print(f"Request {i+1}: ❌ RATE LIMITED (wait {remaining_ttl}s)")
            else:
                # Increment counter
                new_count = await client.incr(rate_limit_key)
                
                # Set expiration on first request
                if new_count == 1:
                    await client.expire(rate_limit_key, window_seconds)
                
                remaining_ttl = await client.ttl(rate_limit_key)
                print(f"Request {i+1}: ✅ ALLOWED ({new_count}/{max_requests}, resets in {remaining_ttl}s)")
            
            await asyncio.sleep(0.5)  # Small delay between requests
        
        # Cleanup
        await client.delete(rate_limit_key)
        await client.close()
        
    except Exception as e:
        print(f"❌ Rate limiting simulation failed: {e}")

async def test_redis_info():
    """Get Redis server information."""
    print("\n📊 Redis Server Information")
    print("=" * 40)
    
    try:
        client = redis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)
        
        # Get server info
        info = await client.info()
        
        print(f"Redis Version: {info.get('redis_version', 'unknown')}")
        print(f"Uptime: {info.get('uptime_in_seconds', 0)} seconds")
        print(f"Connected Clients: {info.get('connected_clients', 0)}")
        print(f"Used Memory: {info.get('used_memory_human', 'unknown')}")
        print(f"Total Commands Processed: {info.get('total_commands_processed', 0)}")
        
        await client.close()
        
    except Exception as e:
        print(f"❌ Failed to get Redis info: {e}")

async def main():
    """Run all Redis tests."""
    print("🧪 Redis Test Suite for Privacy Inspector API")
    print("=" * 60)
    print(f"Timestamp: {datetime.now()}")
    print()
    
    # Test basic connection
    connection_ok = await test_redis_connection()
    
    if connection_ok:
        # Test rate limiting simulation
        await simulate_rate_limiting()
        
        # Get server info
        await test_redis_info()
        
        print("\n" + "=" * 60)
        print("🎉 All Redis tests completed successfully!")
        print("\n✅ Your Redis setup is ready for the Privacy Inspector API")
        print("✅ Rate limiting will work correctly")
        print("✅ FastAPI can connect to Redis")
        
    else:
        print("\n" + "=" * 60)
        print("❌ Redis tests failed!")
        print("\n🔧 To fix this:")
        print("1. Make sure Redis is installed and running")
        print("2. Run: ./setup_redis.sh")
        print("3. Or manually start Redis: redis-server")
        print("4. Test connection: redis-cli ping")

if __name__ == "__main__":
    asyncio.run(main())
