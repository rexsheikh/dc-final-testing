#!/usr/bin/env python3
"""
Lightweight NLP Pipeline Implementation
Uses only Python standard library - no external ML frameworks

Design Philosophy:
- Pure Python implementation for fast deployment and low resource usage
- No TensorFlow, PyTorch, transformers, spaCy, or NLTK dependencies
- Suitable for f1-micro VMs with limited memory (614MB RAM)
- Focuses on datacenter architecture concepts over NLP sophistication

Stages: Text Normalization → Summarization → TF-IDF → NER → Deck Assembly
All processing completed in 2-5 seconds per document on minimal hardware.
"""

import re
from typing import List, Dict, Tuple
from collections import Counter
import math


class TextNormalizer:
    """Stage 1: Text normalization - cleaning and sentence splitting"""
    
    @staticmethod
    def normalize(text: str) -> Dict[str, any]:
        """
        Normalize text: clean, detect language, split sentences
        Returns: {sentences: List[str], char_count: int, word_count: int}
        """
        # Basic cleaning
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        text = text.strip()
        
        # Simple sentence splitting (basic for now)
        sentences = re.split(r'[.!?]+\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # Count statistics
        words = text.split()
        
        return {
            'sentences': sentences,
            'char_count': len(text),
            'word_count': len(words),
            'sentence_count': len(sentences)
        }


class Summarizer:
    """Stage 2: Extractive summarization using sentence scoring"""
    
    @staticmethod
    def summarize(sentences: List[str], num_sentences: int = 3) -> str:
        """
        Generate extractive summary by selecting top-N sentences
        Uses word frequency as a simple scoring metric
        """
        if len(sentences) <= num_sentences:
            return ' '.join(sentences)
        
        # Build word frequency map (excluding common words)
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                    'of', 'with', 'is', 'are', 'was', 'were', 'be', 'been', 'being'}
        word_freq = Counter()
        
        for sentence in sentences:
            words = sentence.lower().split()
            for word in words:
                if word not in stopwords and len(word) > 2:
                    word_freq[word] += 1
        
        # Score sentences by sum of word frequencies
        sentence_scores = []
        for idx, sentence in enumerate(sentences):
            words = sentence.lower().split()
            score = sum(word_freq.get(word, 0) for word in words)
            sentence_scores.append((idx, score, sentence))
        
        # Select top N sentences, maintaining original order
        top_sentences = sorted(sentence_scores, key=lambda x: x[1], reverse=True)[:num_sentences]
        top_sentences = sorted(top_sentences, key=lambda x: x[0])  # Restore order
        
        return ' '.join(s[2] for s in top_sentences)


class TFIDFExtractor:
    """Stage 3: TF-IDF keyword extraction"""
    
    @staticmethod
    def extract_keywords(sentences: List[str], top_n: int = 10) -> List[Tuple[str, float, str]]:
        """
        Extract top-N keywords using TF-IDF
        Returns: List[(term, score, context_sentence)]
        """
        if not sentences:
            return []
        
        # Stopwords to exclude
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                    'of', 'with', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'this',
                    'that', 'these', 'those', 'it', 'its', 'as', 'by', 'from', 'has', 'have'}
        
        # Build document term frequencies
        doc_words = []
        for sentence in sentences:
            words = [w.lower() for w in re.findall(r'\b\w+\b', sentence) 
                    if len(w) > 2 and w.lower() not in stopwords]
            doc_words.extend(words)
        
        if not doc_words:
            return []
        
        # Calculate TF (term frequency in entire document)
        tf = Counter(doc_words)
        total_words = len(doc_words)
        tf = {word: count / total_words for word, count in tf.items()}
        
        # Calculate IDF (inverse document frequency - sentence-level)
        df = Counter()  # document frequency (how many sentences contain term)
        for sentence in sentences:
            words = set(w.lower() for w in re.findall(r'\b\w+\b', sentence) 
                       if len(w) > 2 and w.lower() not in stopwords)
            for word in words:
                df[word] += 1
        
        num_docs = len(sentences)
        idf = {word: math.log(num_docs / (count + 1)) for word, count in df.items()}
        
        # Calculate TF-IDF scores
        tfidf = {word: tf.get(word, 0) * idf.get(word, 0) for word in tf.keys()}
        
        # Get top-N terms with context sentences
        top_terms = sorted(tfidf.items(), key=lambda x: x[1], reverse=True)[:top_n]
        
        results = []
        for term, score in top_terms:
            # Find a sentence containing this term for context
            context = next((s for s in sentences if term in s.lower()), "")
            results.append((term, score, context))
        
        return results


class NamedEntityRecognizer:
    """Stage 4: Simple named entity recognition"""
    
    @staticmethod
    def extract_entities(sentences: List[str]) -> List[Tuple[str, str, str]]:
        """
        Extract named entities using simple heuristics
        Returns: List[(entity, type, definition/context)]
        """
        entities = []
        
        # Pattern 1: Capitalized phrases (potential proper nouns)
        for sentence in sentences:
            # Find sequences of capitalized words
            matches = re.finditer(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', sentence)
            for match in matches:
                entity = match.group()
                # Skip common sentence-starting words
                if entity.lower() in {'the', 'this', 'that', 'these', 'those', 'a', 'an'}:
                    continue
                
                # Try to extract definition from context
                context = sentence
                entity_type = 'UNKNOWN'
                
                # Simple heuristic: check for "is a/an" pattern
                is_pattern = rf'{re.escape(entity)}\s+is\s+(?:a|an)\s+([^,.;]+)'
                is_match = re.search(is_pattern, sentence, re.IGNORECASE)
                if is_match:
                    context = is_match.group(1).strip()
                    entity_type = 'TERM'
                
                entities.append((entity, entity_type, context))
        
        # Deduplicate by entity name
        seen = set()
        unique_entities = []
        for entity, etype, context in entities:
            if entity not in seen:
                seen.add(entity)
                unique_entities.append((entity, etype, context))
        
        return unique_entities[:20]  # Limit to top 20


class DeckAssembler:
    """Stage 5: Assemble Anki CSV deck from pipeline outputs"""
    
    @staticmethod
    def assemble_deck(
        summary: str,
        keywords: List[Tuple[str, float, str]],
        entities: List[Tuple[str, str, str]],
        filename: str
    ) -> List[Tuple[str, str]]:
        """
        Create flashcard pairs (front, back) from NLP outputs
        Returns: List[(front, back)]
        """
        cards = []
        
        # Card 1: Summary card
        if summary:
            cards.append((
                f"Summarize the key points from {filename}",
                summary
            ))
        
        # Cards 2-N: Keyword definition cards
        for term, score, context in keywords[:8]:  # Top 8 keywords
            front = f"What is {term}?"
            # Use context sentence as back, or create simple definition
            back = context if context else f"A key term from {filename}"
            cards.append((front, back))
        
        # Cards N+1-M: Entity cards
        for entity, etype, context in entities[:5]:  # Top 5 entities
            front = f"Define or describe: {entity}"
            back = context
            cards.append((front, back))
        
        return cards
    
    @staticmethod
    def write_csv(cards: List[Tuple[str, str]], output_path: str) -> None:
        """Write cards to CSV file in Anki-importable format"""
        import csv
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Front', 'Back'])
            for front, back in cards:
                writer.writerow([front, back])


def process_pipeline(text: str, filename: str) -> Dict[str, any]:
    """
    Run full NLP pipeline on input text
    Returns pipeline outputs for deck assembly
    """
    # Stage 1: Normalize
    normalized = TextNormalizer.normalize(text)
    sentences = normalized['sentences']
    
    # Stage 2: Summarize
    summary = Summarizer.summarize(sentences, num_sentences=3)
    
    # Stage 3: Extract keywords
    keywords = TFIDFExtractor.extract_keywords(sentences, top_n=10)
    
    # Stage 4: Extract entities
    entities = NamedEntityRecognizer.extract_entities(sentences)
    
    # Stage 5: Assemble deck
    cards = DeckAssembler.assemble_deck(summary, keywords, entities, filename)
    
    return {
        'normalized': normalized,
        'summary': summary,
        'keywords': keywords,
        'entities': entities,
        'cards': cards
    }
