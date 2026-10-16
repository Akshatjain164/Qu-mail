import os
import json
import logging

logger = logging.getLogger(__name__)
_supabase_client = None

def _get_client():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    
    try:
        from config import Config
        try:
            from supabase import create_client, Client
        except ImportError:
            logger.warning("Supabase python client not installed")
            return None

        url = Config.SUPABASE_CONFIG.get("url", "")
        key = Config.SUPABASE_CONFIG.get("key", "")
        if not url or not key or url.startswith("YOUR_"):
            logger.error("❌ Supabase URL or Key not configured – check config.py / env vars")
            return None

        _supabase_client = create_client(url, key)
        logger.info("✅ Supabase client initialised")
        return _supabase_client
    except Exception as e:
        logger.error(f"❌ Supabase client init failed: {e}")
        return None

class SupabaseStorage:
    def __init__(self):
        self.client = _get_client()
        self._memory_cache = {}
        self._memory_user_keys = {}

    def is_connected(self) -> bool:
        if not self.client:
            return False
        try:
            self.client.table("user_keys").select("id").limit(1).execute()
            return True
        except Exception:
            return False

    def set_user_key(self, user_email: str, key_id: str, key_data: dict):
        if user_email not in self._memory_user_keys:
            self._memory_user_keys[user_email] = {}
        self._memory_user_keys[user_email][key_id] = key_data

        if not self.client:
            return False
        
        try:
            self.client.table("user_keys").upsert(
                {
                    "user_email": user_email,
                    "key_id": key_id,
                    "data": key_data
                },
                on_conflict="user_email,key_id"
            ).execute()
            return True
        except Exception as e:
            error_str = str(e)
            if '23505' in error_str or 'duplicate' in error_str.lower():
                logger.debug(f"Key {key_id} already exists for {user_email} (ok)")
                return True
            logger.error(f"❌ Supabase set_user_key error: {e}")
            return False

    def get_user_key(self, user_email: str, key_id: str):
        if not self.client:
            return self._memory_user_keys.get(user_email, {}).get(key_id)
        
        try:
            resp = (
                self.client.table("user_keys")
                .select("data")
                .eq("user_email", user_email)
                .eq("key_id", key_id)
                .execute()
            )
            if resp.data and len(resp.data) > 0:
                return resp.data[0]["data"]
        except Exception as e:
            logger.error(f"❌ Supabase get_user_key error: {e}")
            
        return self._memory_user_keys.get(user_email, {}).get(key_id)

    def get_all_user_keys(self, user_email: str):
        if not self.client:
            return self._memory_user_keys.get(user_email, {})
        try:
            resp = (
                self.client.table("user_keys")
                .select("key_id, data")
                .eq("user_email", user_email)
                .execute()
            )
            return {row["key_id"]: row["data"] for row in (resp.data or [])}
        except Exception as e:
            logger.error(f"❌ Supabase get_all_user_keys({user_email}) error: {e}")
            return self._memory_user_keys.get(user_email, {})

    def count_user_keys(self, user_email: str) -> int:
        if not self.client:
            return len(self._memory_user_keys.get(user_email, {}))
        try:
            resp = (
                self.client.table("user_keys")
                .select("key_id", count="exact")
                .eq("user_email", user_email)
                .execute()
            )
            return resp.count if resp.count is not None else 0
        except Exception as e:
            logger.error(f"❌ Supabase count_user_keys({user_email}) error: {e}")
            return len(self._memory_user_keys.get(user_email, {}))

    def delete_user_key(self, user_email: str, key_id: str):
        if user_email in self._memory_user_keys and key_id in self._memory_user_keys[user_email]:
            del self._memory_user_keys[user_email][key_id]

        if not self.client:
            return False
        try:
            (
                self.client.table("user_keys")
                .delete()
                .eq("user_email", user_email)
                .eq("key_id", key_id)
                .execute()
            )
            return True
        except Exception as e:
            logger.error(f"❌ Supabase delete_user_key({user_email}/{key_id}) error: {e}")
            return False

supabase_storage = SupabaseStorage()
