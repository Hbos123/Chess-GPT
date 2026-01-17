import unittest

from llm_router import LLMRouter, LLMRouterConfig


class TestVLLMHealthProbe(unittest.TestCase):
    def test_vllm_health_probe_raises_when_models_list_fails(self):
        router = LLMRouter(LLMRouterConfig(vllm_health_ttl_seconds=0.0))

        original = router.vllm_client.models.list

        def boom():
            raise RuntimeError("nope")

        try:
            router.vllm_client.models.list = boom  # type: ignore[assignment]
            with self.assertRaises(RuntimeError) as ctx:
                router.check_vllm_health(force=True)
            self.assertIn("vLLM health check failed", str(ctx.exception))
        finally:
            router.vllm_client.models.list = original  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main()


