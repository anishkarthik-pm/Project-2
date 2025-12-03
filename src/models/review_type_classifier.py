"""
Review Type Classifier using Google Gemini Flash API.

Classifies app reviews into specific types:
- Bug Report
- Feature Request
- Positive Feedback
- Negative Feedback
- Pricing/Value Concern
- Customer Support Issue
- Transaction/Payment Issue
- Security/Trust Concern
- Performance Issue
- UI/UX Issue
"""

import json
import logging
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Review type categories
REVIEW_TYPES = [
    "Bug Report",
    "Feature Request",
    "Positive Feedback",
    "Negative Feedback",
    "Pricing/Value Concern",
    "Customer Support Issue",
    "Transaction/Payment Issue",
    "Security/Trust Concern",
    "Performance Issue",
    "UI/UX Issue"
]


class ReviewTypeClassifier:
    """
    Classifier for categorizing app reviews into predefined types.
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.0-flash",
        temperature: float = 0.1
    ):
        """
        Initialize the classifier.

        Args:
            api_key: Google Gemini API key
            model_name: Model to use (default: gemini-2.0-flash)
            temperature: Temperature for generation (0.0-1.0)
        """
        genai.configure(api_key=api_key)

        self.model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature
            )
        )

        self.prompt_template = self._get_prompt_template()
        logger.info(f"Initialized ReviewTypeClassifier with model: {model_name}")

    def _get_prompt_template(self) -> str:
        """
        Get the classification prompt template.

        Returns:
            Prompt string
        """
        return f"""You are an expert at categorizing app store reviews.

Your task is to classify each review into ONE of these review types:

{', '.join(REVIEW_TYPES)}

DEFINITIONS:
- Bug Report: User reports a technical issue, crash, or malfunction
- Feature Request: User asks for new functionality or improvements
- Positive Feedback: User praises the app, expresses satisfaction
- Negative Feedback: General complaint without specific category
- Pricing/Value Concern: User complains about cost, pricing, or value
- Customer Support Issue: User mentions problems with support/service
- Transaction/Payment Issue: Problems with payments, withdrawals, deposits
- Security/Trust Concern: User worried about security, data safety, trust
- Performance Issue: App is slow, laggy, takes too long to load
- UI/UX Issue: User interface problems, confusing navigation, design issues

INSTRUCTIONS:
1. Read each review carefully
2. Assign the MOST APPROPRIATE review type
3. Return ONLY valid JSON in this exact format:

{{"classifications": [
  {{"review_index": 0, "review_type": "Bug Report"}},
  {{"review_index": 1, "review_type": "Positive Feedback"}}
]}}

REVIEWS TO CLASSIFY:
{{reviews}}

Return ONLY the JSON object, no other text."""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _call_api(self, reviews_text: str) -> str:
        """
        Call Gemini API with retry logic.

        Args:
            reviews_text: Formatted reviews string

        Returns:
            API response text
        """
        prompt = self.prompt_template.replace("{reviews}", reviews_text)
        response = self.model.generate_content(prompt)
        return response.text

    def classify_batch(
        self,
        reviews: List[Dict[str, Any]],
        batch_size: int = 10
    ) -> List[str]:
        """
        Classify a batch of reviews into review types.

        Args:
            reviews: List of review dicts with 'content' field
            batch_size: Number of reviews per API call

        Returns:
            List of review types in same order as input
        """
        if not reviews:
            return []

        all_types = []

        for i in range(0, len(reviews), batch_size):
            batch = reviews[i:i + batch_size]

            # Format reviews for prompt
            reviews_text = "\n\n".join([
                f"Review {j}: {review.get('content', '')}"
                for j, review in enumerate(batch)
            ])

            try:
                # Call API
                response_text = self._call_api(reviews_text)

                # Parse JSON response
                response_text = response_text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()

                result = json.loads(response_text)
                classifications = result.get("classifications", [])

                # Extract review types
                batch_types = []
                for item in classifications:
                    review_type = item.get("review_type", "Negative Feedback")

                    # Validate review type
                    if review_type not in REVIEW_TYPES:
                        logger.warning(f"Invalid review type '{review_type}', defaulting to 'Negative Feedback'")
                        review_type = "Negative Feedback"

                    batch_types.append(review_type)

                # Handle mismatched lengths
                while len(batch_types) < len(batch):
                    batch_types.append("Negative Feedback")

                all_types.extend(batch_types[:len(batch)])

                logger.debug(f"Classified batch {i//batch_size + 1}: {len(batch)} reviews")

            except Exception as e:
                logger.error(f"Error classifying batch {i//batch_size + 1}: {e}")
                # Default to "Negative Feedback" for failed batch
                all_types.extend(["Negative Feedback"] * len(batch))

            # Rate limiting
            time.sleep(0.5)

        return all_types

    def classify_single(self, review_text: str) -> str:
        """
        Classify a single review.

        Args:
            review_text: Review text

        Returns:
            Review type
        """
        reviews = [{"content": review_text}]
        types = self.classify_batch(reviews, batch_size=1)
        return types[0] if types else "Negative Feedback"


def get_review_type_distribution(review_types: List[str]) -> Dict[str, int]:
    """
    Get distribution of review types.

    Args:
        review_types: List of review type labels

    Returns:
        Dictionary mapping review type to count
    """
    distribution = {rt: 0 for rt in REVIEW_TYPES}

    for rt in review_types:
        if rt in distribution:
            distribution[rt] += 1

    return distribution
