#!/usr/bin/env python3
"""
Flesch-Kincaid Grade Level Analysis + Lightweight NLP Pipeline
Pure Python implementation - no external dependencies

Features:
- Flesch-Kincaid readability + complexity metrics
- Lightweight NLP pipeline (normalization, TF-IDF, NER)
- DeckAssembler for generating Anki-compatible CSV decks
"""

import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple


def count_syllables(word: str) -> int:
    """
    Count syllables in a word using simple heuristic
    
    Args:
        word: Input word
        
    Returns:
        Number of syllables
    """
    word = word.lower()
    vowels = 'aeiouy'
    syllable_count = 0
    previous_was_vowel = False
    
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not previous_was_vowel:
            syllable_count += 1
        previous_was_vowel = is_vowel
    
    # Adjust for silent 'e'
    if word.endswith('e'):
        syllable_count -= 1
    
    # Ensure at least 1 syllable
    if syllable_count == 0:
        syllable_count = 1
    
    return syllable_count


def flesch_kincaid_analysis(text: str, top_n: int = 20) -> Dict:
    """
    Analyze text using Flesch-Kincaid Grade Level formula
    and identify words with highest complexity scores
    
    Formula: 0.39 × (total words / total sentences) + 11.8 × (total syllables / total words) - 15.59
    
    Args:
        text: Input text string
        top_n: Number of most complex words to return
        
    Returns:
        Dictionary with FK grade level and complex words
    """
    # Split into sentences (basic splitting on .!?)
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # Extract words (alphabetic only)
    words = re.findall(r'\b[a-zA-Z]+\b', text)
    words = [word.lower() for word in words]
    
    # Calculate metrics
    total_sentences = len(sentences)
    total_words = len(words)
    total_syllables = sum(count_syllables(word) for word in words)
    
    # Flesch-Kincaid Grade Level formula
    if total_sentences > 0 and total_words > 0:
        fk_grade = (0.39 * (total_words / total_sentences) + 
                   11.8 * (total_syllables / total_words) - 15.59)
    else:
        fk_grade = 0
    
    # Calculate complexity score for each unique word
    word_complexity = {}
    for word in set(words):
        if len(word) > 2:  # Skip very short words
            syllables = count_syllables(word)
            # Complexity: syllables × length
            complexity = syllables * len(word)
            word_complexity[word] = {
                'complexity': complexity,
                'syllables': syllables,
                'length': len(word)
            }
    
    # Get top N most complex words
    sorted_words = sorted(word_complexity.items(), 
                        key=lambda x: x[1]['complexity'], 
                        reverse=True)[:top_n]
    
    complex_words = [
        {
            'word': word,
            'syllables': data['syllables'],
            'length': data['length'],
            'complexity_score': data['complexity']
        }
        for word, data in sorted_words
    ]
    
    return {
        'flesch_kincaid_grade': round(fk_grade, 2),
        'total_sentences': total_sentences,
        'total_words': total_words,
        'total_syllables': total_syllables,
        'avg_words_per_sentence': round(total_words / total_sentences, 2) if total_sentences > 0 else 0,
        'avg_syllables_per_word': round(total_syllables / total_words, 2) if total_words > 0 else 0,
        'complex_words': complex_words
    }


class TextNormalizer:
    """Stage 1: Text normalization - cleaning and sentence splitting"""

    @staticmethod
    def normalize(text: str) -> Dict[str, Any]:
        """
        Normalize text: clean it, split into sentences, and collect stats.
        Returns: {sentences: List[str], char_count: int, word_count: int}
        """
        text = re.sub(r'\s+', ' ', text).strip()
        sentences = re.split(r'[.!?]+\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        words = text.split()

        return {
            'sentences': sentences,
            'char_count': len(text),
            'word_count': len(words),
            'sentence_count': len(sentences)
        }


class TFIDFExtractor:
    """Stage 2: TF-IDF keyword extraction"""

    @staticmethod
    def extract_keywords(sentences: List[str], top_n: int = 10) -> List[Tuple[str, float, str]]:
        """
        Extract top-N keywords using TF-IDF and capture a context sentence
        Returns: List[(term, score, context_sentence)]
        """
        if not sentences:
            return []

        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'this',
            'that', 'these', 'those', 'it', 'its', 'as', 'by', 'from', 'has', 'have'
        }

        doc_words: List[str] = []
        for sentence in sentences:
            words = [
                w.lower()
                for w in re.findall(r'\b\w+\b', sentence)
                if len(w) > 2 and w.lower() not in stopwords
            ]
            doc_words.extend(words)

        if not doc_words:
            return []

        tf_counts = Counter(doc_words)
        total_words = len(doc_words)
        tf = {word: count / total_words for word, count in tf_counts.items()}

        df = Counter()
        for sentence in sentences:
            words = {
                w.lower()
                for w in re.findall(r'\b\w+\b', sentence)
                if len(w) > 2 and w.lower() not in stopwords
            }
            for word in words:
                df[word] += 1

        num_docs = len(sentences)
        idf = {word: math.log(num_docs / (count + 1)) for word, count in df.items()}

        tfidf = {word: tf.get(word, 0) * idf.get(word, 0) for word in tf.keys()}
        top_terms = sorted(tfidf.items(), key=lambda x: x[1], reverse=True)[:top_n]

        results: List[Tuple[str, float, str]] = []
        for term, score in top_terms:
            context = next((s for s in sentences if term in s.lower()), "")
            results.append((term, score, context))

        return results


class NamedEntityRecognizer:
    """Stage 3: Simple named entity recognition"""

    @staticmethod
    def extract_entities(sentences: List[str]) -> List[Tuple[str, str, str]]:
        """
        Extract named entities using simple heuristics
        Returns: List[(entity, type, definition/context)]
        """
        entities: List[Tuple[str, str, str]] = []

        for sentence in sentences:
            matches = re.finditer(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', sentence)
            for match in matches:
                entity = match.group()
                if entity.lower() in {'the', 'this', 'that', 'these', 'those', 'a', 'an'}:
                    continue

                context = sentence
                entity_type = 'UNKNOWN'

                is_pattern = rf'{re.escape(entity)}\s+is\s+(?:a|an)\s+([^,.;]+)'
                is_match = re.search(is_pattern, sentence, re.IGNORECASE)
                if is_match:
                    context = is_match.group(1).strip()
                    entity_type = 'TERM'

                entities.append((entity, entity_type, context))

        seen = set()
        unique_entities = []
        for entity, entity_type, context in entities:
            if entity not in seen:
                seen.add(entity)
                unique_entities.append((entity, entity_type, context))

        return unique_entities[:20]


class DeckAssembler:
    """Stage 4: Assemble Anki CSV deck from pipeline outputs"""

    @staticmethod
    def assemble_deck(
        keywords: List[Tuple[str, float, str]],
        entities: List[Tuple[str, str, str]],
        filename: str
    ) -> List[Tuple[str, str]]:
        """
        Create flashcard pairs (front, back) from NLP outputs
        Returns: List[(front, back)]
        """
        cards: List[Tuple[str, str]] = []

        for term, _, _ in keywords[:10]:
            cards.append((term, f"(**update with your chosen definition of {term}**)"))

        for entity, _, _ in entities[:5]:
            cards.append((entity, f"(**update with your chosen definition of {entity}**)"))

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


def process_pipeline(text: str, filename: str) -> Dict[str, Any]:
    """
    Run full NLP pipeline on input text
    Returns pipeline outputs for deck assembly
    """
    normalized = TextNormalizer.normalize(text)
    sentences = normalized['sentences']
    keywords = TFIDFExtractor.extract_keywords(sentences, top_n=10)
    entities = NamedEntityRecognizer.extract_entities(sentences)
    cards = DeckAssembler.assemble_deck(keywords, entities, filename)

    return {
        'normalized': normalized,
        'keywords': keywords,
        'entities': entities,
        'cards': cards
    }


def write_complex_word_deck(complex_words: List[Dict[str, Any]], output_path: str) -> None:
    """Write CSV deck containing the most complex words from FK analysis."""
    import csv

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Front', 'Back'])
        for item in complex_words:
            word = item['word']
            writer.writerow([
                word,
                f"(**add your own definition/example for {word}**)"
            ])


def main():
    """Main entry point for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Flesch-Kincaid Grade Level Analysis'
    )
    parser.add_argument(
        'file',
        help='Input text file'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=50000,
        help='Maximum characters to process (default: 50000, 0=no limit)'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=20,
        help='Number of most complex words to show (default: 20)'
    )
    parser.add_argument(
        '--deck-output',
        type=str,
        help='Optional path to write the complex-word CSV deck'
    )
    parser.add_argument(
        '--generate-deck',
        action='store_true',
        help='Create a deck CSV of the most complex words (default path is current directory)'
    )
    
    args = parser.parse_args()
    
    # Read file
    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            text = f.read()
    except FileNotFoundError:
        print(f"Error: File '{args.file}' not found")
        return 1
    
    print(f"File: {args.file}")
    print(f"Original size: {len(text):,} characters")
    
    # Apply limit
    if args.limit > 0 and len(text) > args.limit:
        text = text[:args.limit]
        print(f"Processing: {len(text):,} characters (limited)")
    else:
        print(f"Processing: {len(text):,} characters (full)")
    
    # Analyze
    print("\nAnalyzing...")
    results = flesch_kincaid_analysis(text, top_n=args.top_n)
    
    # Print results
    print("\n" + "="*60)
    print("FLESCH-KINCAID GRADE LEVEL ANALYSIS")
    print("="*60)
    print(f"Grade Level: {results['flesch_kincaid_grade']}")
    print(f"  (requires ~{int(results['flesch_kincaid_grade'])} years of education)")
    
    print(f"\nText Statistics:")
    print(f"  Sentences: {results['total_sentences']:,}")
    print(f"  Words: {results['total_words']:,}")
    print(f"  Syllables: {results['total_syllables']:,}")
    print(f"  Avg words/sentence: {results['avg_words_per_sentence']}")
    print(f"  Avg syllables/word: {results['avg_syllables_per_word']}")
    
    print(f"\nMost Complex Words:")
    for i, item in enumerate(results['complex_words'], 1):
        print(f"  {i}. {item['word']}")
        print(f"     {item['syllables']} syllables, {item['length']} letters, complexity: {item['complexity_score']}")

    if args.generate_deck or args.deck_output:
        print("\nGenerating deck from most complex words...")
        deck_filename = f"{Path(args.file).stem or 'deck'}_complex_words.csv"
        deck_path = args.deck_output or os.path.join(os.getcwd(), deck_filename)
        write_complex_word_deck(results['complex_words'], deck_path)
        print(f"Wrote {len(results['complex_words'])} cards to {deck_path}")
    
    return 0


if __name__ == "__main__":
    exit(main())
