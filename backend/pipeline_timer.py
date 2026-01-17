"""
Pipeline Timer - Track performance metrics for the 4-layer pipeline
"""
import time
from typing import Dict, Any, Optional, List
from collections import defaultdict
from dataclasses import dataclass, field
from contextlib import contextmanager

from llm_pricing import estimate_cost_usd  # Pricing table + cost estimator

# Global timer instance (set by main.py)
_current_timer: Optional['PipelineTimer'] = None

def set_pipeline_timer(timer: 'PipelineTimer'):
    """Set the global pipeline timer instance"""
    global _current_timer
    _current_timer = timer

def get_pipeline_timer() -> Optional['PipelineTimer']:
    """Get the global pipeline timer instance"""
    return _current_timer


@dataclass
class TimingEntry:
    """Single timing entry"""
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def finish(self, metadata: Optional[Dict[str, Any]] = None):
        """Mark timing entry as complete"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        if metadata:
            self.metadata.update(metadata)


class PipelineTimer:
    """
    Tracks timing for each step in the 4-layer pipeline.
    Provides detailed breakdown of where time is spent.
    """
    
    def __init__(self):
        self.entries: List[TimingEntry] = []
        self.active_entries: Dict[str, TimingEntry] = {}
        self.layer_times: Dict[str, float] = defaultdict(float)
        self.step_counts: Dict[str, int] = defaultdict(int)
        self.cache_stats: Dict[str, int] = defaultdict(int)  # hits, misses
        self.engine_stats: Dict[str, Any] = defaultdict(lambda: {"count": 0, "total_time": 0.0})
        self.skill_stats: Dict[str, Any] = defaultdict(lambda: {"count": 0, "total_time": 0.0})
        self.stop_reasons: Dict[str, int] = defaultdict(int)
        # LLM stats are tracked per "layer" name and per model.
        # We track input/output tokens separately so cost estimates are accurate.
        self.llm_stats: Dict[str, Any] = defaultdict(
            lambda: {
                "count": 0,
                "total_time": 0.0,
                "tokens_in": 0,
                "tokens_out": 0,
                "tokens_total": 0,
                "by_model": defaultdict(
                    lambda: {
                        "count": 0,
                        "total_time": 0.0,
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "tokens_total": 0,
                    }
                ),
            }
        )
        
    def start(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start timing an operation. Returns entry_id for later reference."""
        entry_id = f"{name}_{len(self.entries)}"
        entry = TimingEntry(
            name=name,
            start_time=time.time(),
            metadata=metadata or {}
        )
        self.entries.append(entry)
        self.active_entries[entry_id] = entry
        return entry_id
    
    def finish(self, entry_id: str, metadata: Optional[Dict[str, Any]] = None):
        """Finish timing an operation"""
        if entry_id in self.active_entries:
            entry = self.active_entries[entry_id]
            entry.finish(metadata)
            
            # Update layer times
            layer_name = entry.name.split(":")[0] if ":" in entry.name else entry.name
            self.layer_times[layer_name] += entry.duration
            
            # Update step counts
            self.step_counts[entry.name] = self.step_counts.get(entry.name, 0) + 1
            
            del self.active_entries[entry_id]
    
    def record_cache(self, cache_type: str, hit: bool):
        """Record cache hit/miss"""
        if hit:
            self.cache_stats[f"{cache_type}_hits"] += 1
        else:
            self.cache_stats[f"{cache_type}_misses"] += 1
    
    def record_engine(self, operation: str, duration: float, depth: Optional[int] = None):
        """Record engine operation timing"""
        key = f"{operation}" + (f"_d{depth}" if depth else "")
        self.engine_stats[key]["count"] += 1
        self.engine_stats[key]["total_time"] += duration
        if depth:
            self.engine_stats[key]["avg_depth"] = depth

    def record_skill(self, name: str, duration: float):
        key = str(name or "unknown")
        self.skill_stats[key]["count"] += 1
        self.skill_stats[key]["total_time"] += float(duration or 0.0)

    def record_stop_reason(self, reason: str):
        r = str(reason or "unknown")
        self.stop_reasons[r] += 1
    
    def record_llm(
        self,
        layer: str,
        duration: float,
        *,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
        model: Optional[str] = None
    ):
        """Record LLM call timing + token usage (input/output)."""
        key = layer
        self.llm_stats[key]["count"] += 1
        self.llm_stats[key]["total_time"] += duration

        tin = int(tokens_in) if tokens_in is not None else 0
        tout = int(tokens_out) if tokens_out is not None else 0
        self.llm_stats[key]["tokens_in"] += tin
        self.llm_stats[key]["tokens_out"] += tout
        self.llm_stats[key]["tokens_total"] += tin + tout

        if model:
            m = str(model)
            by_model = self.llm_stats[key]["by_model"][m]
            by_model["count"] += 1
            by_model["total_time"] += duration
            by_model["tokens_in"] += tin
            by_model["tokens_out"] += tout
            by_model["tokens_total"] += tin + tout

    @contextmanager
    def span(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Convenience context manager for timing a scoped operation.
        Records an 'error' field on exception.
        """
        entry_id = self.start(name, metadata)
        try:
            yield entry_id
        except Exception as e:
            try:
                self.finish(entry_id, {"error": str(e)})
            finally:
                raise
        else:
            self.finish(entry_id)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all timings"""
        total_time = sum(entry.duration for entry in self.entries if entry.duration)
        
        # Group by layer
        layer_breakdown = {}
        for entry in self.entries:
            if entry.duration:
                layer = entry.name.split(":")[0] if ":" in entry.name else "other"
                if layer not in layer_breakdown:
                    layer_breakdown[layer] = {"total": 0.0, "count": 0, "steps": []}
                layer_breakdown[layer]["total"] += entry.duration
                layer_breakdown[layer]["count"] += 1
                layer_breakdown[layer]["steps"].append({
                    "name": entry.name,
                    "duration": entry.duration,
                    "metadata": entry.metadata
                })
        
        # Calculate cache hit rate
        cache_hit_rate = 0.0
        total_cache_ops = sum(v for k, v in self.cache_stats.items() if "hits" in k or "misses" in k)
        if total_cache_ops > 0:
            total_hits = sum(v for k, v in self.cache_stats.items() if "hits" in k)
            cache_hit_rate = (total_hits / total_cache_ops) * 100
        
        # Calculate engine averages
        engine_avg = {}
        for key, stats in self.engine_stats.items():
            if stats["count"] > 0:
                engine_avg[key] = {
                    "count": stats["count"],
                    "total_time": stats["total_time"],
                    "avg_time": stats["total_time"] / stats["count"]
                }
        
        # Calculate LLM averages
        llm_avg = {}
        for key, stats in self.llm_stats.items():
            if stats["count"] > 0:
                # Compute cost estimates per model and total.
                model_breakdown: Dict[str, Any] = {}
                total_cost_usd = 0.0
                for model, mstats in stats.get("by_model", {}).items():
                    mc = estimate_cost_usd(model, mstats.get("tokens_in", 0), mstats.get("tokens_out", 0))
                    if mc is not None:
                        total_cost_usd += mc
                    model_breakdown[model] = {
                        "count": mstats.get("count", 0),
                        "total_time": mstats.get("total_time", 0.0),
                        "avg_time": (mstats.get("total_time", 0.0) / mstats.get("count", 1)) if mstats.get("count", 0) else 0.0,
                        "tokens_in": mstats.get("tokens_in", 0),
                        "tokens_out": mstats.get("tokens_out", 0),
                        "tokens_total": mstats.get("tokens_total", 0),
                        "cost_usd": mc,
                    }

                llm_avg[key] = {
                    "count": stats["count"],
                    "total_time": stats["total_time"],
                    "avg_time": stats["total_time"] / stats["count"],
                    "tokens_in": stats.get("tokens_in", 0),
                    "tokens_out": stats.get("tokens_out", 0),
                    "tokens_total": stats.get("tokens_total", 0),
                    "cost_usd": total_cost_usd if total_cost_usd > 0 else None,
                    "by_model": model_breakdown,
                }
        
        return {
            "total_time": total_time,
            "layer_breakdown": layer_breakdown,
            "cache_stats": dict(self.cache_stats),
            "cache_hit_rate": cache_hit_rate,
            "engine_stats": engine_avg,
            "llm_stats": llm_avg,
            "skill_stats": dict(self.skill_stats),
            "stop_reasons": dict(self.stop_reasons),
            "step_counts": dict(self.step_counts)
        }
    
    def print_summary(self):
        """Print formatted summary to console"""
        summary = self.get_summary()
        vllm_only = str(__import__("os").getenv("VLLM_ONLY", "true")).lower().strip() == "true"
        vllm_model = __import__("os").getenv("VLLM_MODEL", "vllm")

        def _display_model_name(m: str) -> str:
            # In vLLM-only deployments, upstream code may still label stages with OpenAI model names.
            # Avoid misleading logs by hiding those names.
            s = str(m or "")
            if vllm_only and s.lower().startswith("gpt-"):
                return str(vllm_model or "vllm")
            return s
        
        print(f"\n{'='*80}")
        print(f"⏱️  PIPELINE TIMING SUMMARY")
        print(f"{'='*80}")
        print(f"Total Time: {summary['total_time']:.2f}s")
        print(f"\n📊 Layer Breakdown:")
        for layer, data in summary["layer_breakdown"].items():
            percentage = (data["total"] / summary["total_time"] * 100) if summary["total_time"] > 0 else 0
            print(f"   {layer:20s} {data['total']:6.2f}s ({percentage:5.1f}%) - {data['count']} operations")
            # Show top 3 slowest steps
            sorted_steps = sorted(data["steps"], key=lambda x: x["duration"], reverse=True)[:3]
            for step in sorted_steps:
                print(f"      └─ {step['name']:40s} {step['duration']:.2f}s")
        
        if summary["cache_stats"]:
            print(f"\n💾 Cache Stats:")
            print(f"   Hit Rate: {summary['cache_hit_rate']:.1f}%")
            for key, value in summary["cache_stats"].items():
                print(f"   {key:20s} {value}")
        
        if summary["engine_stats"]:
            print(f"\n🔧 Engine Stats:")
            for key, stats in summary["engine_stats"].items():
                print(f"   {key:20s} {stats['count']:3d} calls, {stats['total_time']:6.2f}s total, {stats['avg_time']:.2f}s avg")

        if summary.get("skill_stats"):
            print(f"\n🧩 Skill Stats:")
            for key, stats in sorted(summary["skill_stats"].items(), key=lambda kv: -kv[1].get("total_time", 0.0)):
                print(f"   {key:20s} {stats['count']:3d} calls, {stats['total_time']:6.2f}s total")

        if summary.get("stop_reasons"):
            print(f"\n🛑 Stop Reasons:")
            for key, c in sorted(summary["stop_reasons"].items(), key=lambda kv: -kv[1]):
                print(f"   {key:40s} {c}")
        
        if summary["llm_stats"]:
            print(f"\n🤖 LLM Stats:")
            for key, stats in summary["llm_stats"].items():
                tin = stats.get("tokens_in", 0) or 0
                tout = stats.get("tokens_out", 0) or 0
                ttot = stats.get("tokens_total", 0) or 0
                cost = stats.get("cost_usd", None)

                cost_str = f", ${cost:.4f} est" if isinstance(cost, (int, float)) else ""
                per_100_str = f" (~${cost * 100 / stats['count']:.4f} per 100)" if isinstance(cost, (int, float)) and stats.get("count") else ""
                print(
                    f"   {key:20s} {stats['count']:3d} calls, {stats['total_time']:6.2f}s total, {stats['avg_time']:.2f}s avg"
                    f", in={tin} tok, out={tout} tok, total={ttot} tok{cost_str}{per_100_str}"
                )

                # Per-model breakdown (useful when a layer uses multiple models)
                by_model = stats.get("by_model") or {}
                for model_name, mstats in sorted(by_model.items(), key=lambda kv: (-(kv[1].get("count", 0)), kv[0])):
                    shown = _display_model_name(model_name)
                    mc = mstats.get("cost_usd", None)
                    mc_str = f"${mc:.4f}" if isinstance(mc, (int, float)) else "unknown"
                    per_100 = (mc * 100 / mstats["count"]) if isinstance(mc, (int, float)) and mstats.get("count") else None
                    per_100_m = f" (~${per_100:.4f}/100)" if per_100 is not None else ""
                    print(
                        f"      └─ {shown:18s} {mstats.get('count', 0):3d} calls"
                        f", in={mstats.get('tokens_in', 0)} out={mstats.get('tokens_out', 0)}"
                        f", cost={mc_str}{per_100_m}"
                    )
        
        print(f"{'='*80}\n")

