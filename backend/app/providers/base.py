from typing import Protocol

from app.schemas.analysis import AnalysisPrompt, GroundedAnalysisDraft


class AnalysisProviderError(RuntimeError):
    pass


class AnalysisProviderNotConfigured(AnalysisProviderError):
    pass


class AnalysisProvider(Protocol):
    async def generate(self, prompt: AnalysisPrompt) -> GroundedAnalysisDraft: ...
