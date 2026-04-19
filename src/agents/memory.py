import json
import os
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


class AgentMemory:
	"""Shared FAISS memory for all agents — Agent Zero."""

	def __init__(self, embedding_model: str = "all-MiniLM-L6-v2", faiss_path: str = "data/faiss_memory"):
		self.faiss_path = faiss_path
		self.embeddings = HuggingFaceEmbeddings(model_name=embedding_model)

		if os.path.exists(faiss_path):
			self.db = FAISS.load_local(faiss_path, self.embeddings, allow_dangerous_deserialization=True)
		else:
			self.db = FAISS.from_texts(["init"], embedding=self.embeddings)
			os.makedirs(faiss_path, exist_ok=True)
			self.db.save_local(faiss_path)

	def store_event_analysis(self, event_id: str, agent_name: str, analysis: dict):
		text = f"Event: {event_id}\nAgent: {agent_name}\nAnalysis: {json.dumps(analysis)}"
		self.db.add_texts([text], metadatas=[{"event_id": event_id, "agent": agent_name}])
		self.db.save_local(self.faiss_path)

	def retrieve_event_context(self, query: str, top_k: int = 5) -> list[str]:
		results = self.db.similarity_search(query, k=top_k)
		return [doc.page_content for doc in results]

	def get_compound_risk_context(self, event_ids: list[str]) -> str:
		context = []
		for eid in event_ids:
			context.extend(self.retrieve_event_context(query=f"Event: {eid}", top_k=3))
		return "\n".join(context)
