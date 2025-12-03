"""
NLP Processing Module for Text Analysis
Implements TF-IDF extraction and Named Entity Recognition with POS tagging
"""

import nltk
nltk.download('maxent_ne_chunker_tab')
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tag import pos_tag
from nltk.chunk import ne_chunk
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import os
from typing import List, Dict, Tuple
from collections import defaultdict
import argparse


class NLPProcessor:
    """Main class for NLP processing operations"""
    
    def __init__(self, top_n: int = 10):
        """
        Initialize NLP Processor
        
        Args:
            top_n: Number of top TF-IDF tokens to extract (default: 10)
        """
        self.top_n = top_n
        self.lemmatizer = WordNetLemmatizer()
        
        # Download required NLTK data
        self._download_nltk_data()
        
        # Initialize stopwords
        try:
            self.stop_words = set(stopwords.words('english'))
        except LookupError:
            nltk.download('stopwords')
            self.stop_words = set(stopwords.words('english'))
    
    def _download_nltk_data(self):
        """Download required NLTK datasets"""
        required_datasets = [
            'punkt',
            'stopwords',
            'wordnet',
            'averaged_perceptron_tagger',
            'maxent_ne_chunker',
            'words',
            'punkt_tab',
            'averaged_perceptron_tagger_eng'
        ]
        
        for dataset in required_datasets:
            try:
                nltk.data.find(f'tokenizers/{dataset}')
            except LookupError:
                try:
                    nltk.download(dataset, quiet=True)
                except:
                    pass  # Some datasets may not be available
    
    def count_syllables(self, word: str) -> int:
        """Count syllables in a word using simple heuristic"""
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
    
    def preprocess_text(self, text: str) -> str:
        """
        Preprocess text: tokenize, remove stopwords, lemmatize
        
        Args:
            text: Input text string
            
        Returns:
            Preprocessed text string
        """
        # Tokenize
        tokens = word_tokenize(text.lower())
        
        # Remove stopwords and non-alphabetic tokens
        tokens = [token for token in tokens 
                 if token.isalpha() and token not in self.stop_words]
        
        # Lemmatize
        tokens = [self.lemmatizer.lemmatize(token) for token in tokens]
        
        return ' '.join(tokens)
    
    def extract_tfidf(self, texts: List[str], filenames: List[str] = None) -> List[Dict]:
        """
        Extract top-N TF-IDF tokens from multiple text documents
        
        Args:
            texts: List of text documents
            filenames: Optional list of filenames for reference
            
        Returns:
            List of dictionaries containing top TF-IDF tokens per document
        """
        if not texts:
            return []
        
        # Preprocess texts
        preprocessed_texts = [self.preprocess_text(text) for text in texts]
        
        # Create TF-IDF vectorizer with stopwords excluded
        # Adjust min_df and max_df based on number of documents
        n_docs = len(preprocessed_texts)
        vectorizer = TfidfVectorizer(
            max_features=1000,
            min_df=1,
            max_df=max(0.8, 1.0) if n_docs == 1 else 0.8,  # Use 1.0 for single document
            use_idf=True,
            stop_words='english'  # Explicitly exclude stopwords
        )
        
        # Fit and transform
        tfidf_matrix = vectorizer.fit_transform(preprocessed_texts)
        feature_names = vectorizer.get_feature_names_out()
        
        # Extract top-N for each document
        results = []
        for idx, doc_vector in enumerate(tfidf_matrix):
            # Get TF-IDF scores for this document
            scores = doc_vector.toarray()[0]
            
            # Filter out indices with very common patterns
            # Prioritize tokens with moderate-to-high TF-IDF (uncommon words)
            filtered_indices = [i for i, score in enumerate(scores) if score > 0]
            
            # Sort by TF-IDF score
            sorted_indices = sorted(filtered_indices, key=lambda i: scores[i], reverse=True)
            
            # Get top-N highest TF-IDF (most distinctive/uncommon)
            top_indices = sorted_indices[:self.top_n]
            
            # Get bottom-N lowest TF-IDF (rarest words that still appear)
            # These are often difficult/specialized vocabulary
            bottom_indices = sorted_indices[-self.top_n:] if len(sorted_indices) > self.top_n else []
            
            # Create result dictionary for top tokens
            top_tokens = [
                {
                    'token': feature_names[i],
                    'tfidf_score': float(scores[i])
                }
                for i in top_indices
            ]
            
            # Create result dictionary for rare tokens (lowest TF-IDF)
            rare_tokens = [
                {
                    'token': feature_names[i],
                    'tfidf_score': float(scores[i])
                }
                for i in bottom_indices
            ]
            
            result = {
                'document_index': idx,
                'top_tokens': top_tokens,
                'rare_tokens': rare_tokens  # Lowest TF-IDF = rarest vocabulary
            }
            
            if filenames and idx < len(filenames):
                result['filename'] = filenames[idx]
            
            results.append(result)
        
        return results
    
    def named_entity_recognition(self, text: str) -> Dict:
        """
        Perform Named Entity Recognition with POS tagging
        
        Args:
            text: Input text string
            
        Returns:
            Dictionary containing entities, POS tags, and analysis
        """
        # Tokenize sentences
        sentences = sent_tokenize(text)
        
        all_entities = []
        all_pos_tags = []
        entity_counts = defaultdict(int)
        pos_counts = defaultdict(int)
        
        for sentence in sentences:
            # Tokenize words
            tokens = word_tokenize(sentence)
            
            # POS tagging
            pos_tags = pos_tag(tokens)
            all_pos_tags.extend(pos_tags)
            
            # Count POS tags
            for token, tag in pos_tags:
                pos_counts[tag] += 1
            
            # Named Entity Recognition
            ne_tree = ne_chunk(pos_tags, binary=False)
            
            # Extract entities
            for subtree in ne_tree:
                if hasattr(subtree, 'label'):
                    entity_type = subtree.label()
                    entity_text = ' '.join([token for token, tag in subtree.leaves()])
                    all_entities.append({
                        'text': entity_text,
                        'type': entity_type,
                        'tokens': [token for token, tag in subtree.leaves()]
                    })
                    entity_counts[entity_type] += 1
        
        # Group entities by type
        entities_by_type = defaultdict(list)
        entity_frequency = defaultdict(int)
        
        for entity in all_entities:
            entities_by_type[entity['type']].append(entity['text'])
            entity_frequency[entity['text']] += 1
        
        # Get top 5 most frequent entities overall
        top_entities = sorted(entity_frequency.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'entities': all_entities,
            'entity_counts': dict(entity_counts),
            'entities_by_type': dict(entities_by_type),
            'entity_frequency': dict(entity_frequency),
            'top_entities': top_entities,
            'pos_tags': all_pos_tags[:100],  # Limit to first 100 for brevity
            'pos_counts': dict(pos_counts),
            'total_entities': len(all_entities),
            'total_tokens': len(all_pos_tags)
        }
    
    def analyze_sentence_structure(self, text: str) -> Dict:
        """
        Analyze sentence structure with detailed POS information
        
        Args:
            text: Input text string
            
        Returns:
            Dictionary with sentence structure analysis
        """
        sentences = sent_tokenize(text)
        sentence_analyses = []
        
        for sentence in sentences[:10]:  # Analyze first 10 sentences
            tokens = word_tokenize(sentence)
            pos_tags = pos_tag(tokens)
            
            # Categorize POS tags
            nouns = [token for token, tag in pos_tags if tag.startswith('NN')]
            verbs = [token for token, tag in pos_tags if tag.startswith('VB')]
            adjectives = [token for token, tag in pos_tags if tag.startswith('JJ')]
            adverbs = [token for token, tag in pos_tags if tag.startswith('RB')]
            
            sentence_analyses.append({
                'sentence': sentence,
                'token_count': len(tokens),
                'nouns': nouns,
                'verbs': verbs,
                'adjectives': adjectives,
                'adverbs': adverbs,
                'pos_tags': pos_tags
            })
        
        return {
            'total_sentences': len(sentences),
            'analyzed_sentences': sentence_analyses
        }
    
    def flesch_kincaid_analysis(self, text: str, top_n: int = 20) -> Dict:
        """
        Analyze text using Flesch-Kincaid Grade Level formula
        and identify words with highest complexity scores
        
        Args:
            text: Input text string
            top_n: Number of most complex words to return
            
        Returns:
            Dictionary with FK grade level and complex words
        """
        # Tokenize
        sentences = sent_tokenize(text)
        words = word_tokenize(text)
        
        # Filter to only alphabetic words
        words = [word.lower() for word in words if word.isalpha()]
        
        # Calculate metrics
        total_sentences = len(sentences)
        total_words = len(words)
        total_syllables = sum(self.count_syllables(word) for word in words)
        
        # Flesch-Kincaid Grade Level formula
        # 0.39 × (total words / total sentences) + 11.8 × (total syllables / total words) - 15.59
        if total_sentences > 0 and total_words > 0:
            fk_grade = (0.39 * (total_words / total_sentences) + 
                       11.8 * (total_syllables / total_words) - 15.59)
        else:
            fk_grade = 0
        
        # Calculate complexity score for each unique word
        word_complexity = {}
        for word in set(words):
            if len(word) > 2:  # Skip very short words
                syllables = self.count_syllables(word)
                # Simplified per-word complexity: favor multi-syllable words
                complexity = syllables * len(word)  # Syllables × length
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


def process_text_file(filepath: str, top_n: int = 10, max_chars: int = None, enable_fk: bool = False) -> Dict:
    """
    Process a single text file with full NLP analysis
    
    Args:
        filepath: Path to text file
        top_n: Number of top TF-IDF tokens
        max_chars: Maximum characters to process (for speed limiting)
        enable_fk: Enable Flesch-Kincaid grade level analysis
        
    Returns:
        Dictionary with complete analysis results
    """
    processor = NLPProcessor(top_n=top_n)
    
    # Read file
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
    
    # Truncate if max_chars specified
    original_length = len(text)
    if max_chars and len(text) > max_chars:
        text = text[:max_chars]
    
    # Perform analyses
    tfidf_results = processor.extract_tfidf([text], [os.path.basename(filepath)])
    ner_results = processor.named_entity_recognition(text)
    sentence_structure = processor.analyze_sentence_structure(text)
    
    result = {
        'filename': os.path.basename(filepath),
        'filepath': filepath,
        'text_length': len(text),
        'tfidf': tfidf_results[0] if tfidf_results else {},
        'named_entities': ner_results,
        'sentence_structure': sentence_structure
    }
    
    # Add Flesch-Kincaid analysis if enabled
    if enable_fk:
        fk_results = processor.flesch_kincaid_analysis(text, top_n=top_n)
        result['flesch_kincaid'] = fk_results
    
    if max_chars and original_length > max_chars:
        result['truncated'] = True
        result['original_length'] = original_length
        result['processed_length'] = len(text)
    
    return result


def process_directory(directory: str, top_n: int = 10, pattern: str = '*.txt', max_chars: int = None, enable_fk: bool = False) -> List[Dict]:
    """
    Process all text files in a directory
    
    Args:
        directory: Directory path
        top_n: Number of top TF-IDF tokens
        pattern: File pattern to match (default: *.txt)
        max_chars: Maximum characters to process per file (for speed limiting)
        
    Returns:
        List of analysis results for each file
    """
    import glob
    
    processor = NLPProcessor(top_n=top_n)
    
    # Find all text files
    search_pattern = os.path.join(directory, pattern)
    text_files = glob.glob(search_pattern)
    
    if not text_files:
        print(f"No files matching pattern '{pattern}' found in {directory}")
        return []
    
    # Read all texts
    texts = []
    filenames = []
    original_lengths = []
    
    for filepath in text_files:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
                original_length = len(text)
                
                # Truncate if max_chars specified
                if max_chars and len(text) > max_chars:
                    text = text[:max_chars]
                
                texts.append(text)
                filenames.append(os.path.basename(filepath))
                original_lengths.append(original_length)
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
    
    # Compute TF-IDF across all documents
    tfidf_results = processor.extract_tfidf(texts, filenames)
    
    # Perform NER on each document
    all_results = []
    for idx, (filepath, text) in enumerate(zip(text_files, texts)):
        ner_results = processor.named_entity_recognition(text)
        
        result = {
            'filename': os.path.basename(filepath),
            'filepath': filepath,
            'text_length': len(text),
            'tfidf': tfidf_results[idx] if idx < len(tfidf_results) else {},
            'named_entities': ner_results
        }
        
        # Add Flesch-Kincaid analysis if enabled
        if enable_fk:
            fk_results = processor.flesch_kincaid_analysis(text, top_n=top_n)
            result['flesch_kincaid'] = fk_results
        
        # Add truncation info if applicable
        if max_chars and original_lengths[idx] > max_chars:
            result['truncated'] = True
            result['original_length'] = original_lengths[idx]
            result['processed_length'] = len(text)
        
        all_results.append(result)
    
    return all_results


def main():
    """Main entry point for command-line usage"""
    parser = argparse.ArgumentParser(
        description='NLP Text Processing: TF-IDF and Named Entity Recognition'
    )
    parser.add_argument(
        'input',
        help='Input text file or directory'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=10,
        help='Number of top TF-IDF tokens to extract (default: 10)'
    )
    parser.add_argument(
        '--fast',
        action='store_true',
        help='Fast mode: limit processing to ~50K characters per file for ~10 second total runtime'
    )
    parser.add_argument(
        '--max-chars',
        type=int,
        help='Maximum characters to process per file (overrides --fast)'
    )
    parser.add_argument(
        '--pattern',
        default='*.txt',
        help='File pattern for directory processing (default: *.txt)'
    )
    parser.add_argument(
        '--output',
        help='Output JSON file (optional)'
    )
    parser.add_argument(
        '--flesch-kincaid',
        action='store_true',
        help='Enable Flesch-Kincaid Grade Level analysis and complex word identification'
    )
    
    args = parser.parse_args()
    
    # Determine max_chars setting
    max_chars = None
    if args.max_chars:
        max_chars = args.max_chars
    elif args.fast:
        max_chars = 50000  # ~50K chars processes in ~10 seconds
    
    if max_chars:
        print(f"Fast mode enabled: processing up to {max_chars} characters per file")
    
    # Process input
    if os.path.isfile(args.input):
        print(f"Processing file: {args.input}")
        results = process_text_file(args.input, top_n=args.top_n, max_chars=max_chars, enable_fk=args.flesch_kincaid)
        
        # Print truncation warning if applicable
        if results.get('truncated'):
            print(f"\n⚠️  Text truncated: {results['original_length']:,} → {results['processed_length']:,} characters")
        
        # Print results
        print("\n" + "="*80)
        print("TF-IDF TOP TOKENS (Most Distinctive)")
        print("="*80)
        if 'tfidf' in results and 'top_tokens' in results['tfidf']:
            for item in results['tfidf']['top_tokens']:
                print(f"  {item['token']}: {item['tfidf_score']:.4f}")
        
        print("\n" + "="*80)
        print("RARE VOCABULARY (Lowest TF-IDF - Difficult Words)")
        print("="*80)
        if 'tfidf' in results and 'rare_tokens' in results['tfidf']:
            if results['tfidf']['rare_tokens']:
                print("These rare words may require dictionary lookup:")
                for item in results['tfidf']['rare_tokens']:
                    print(f"  {item['token']}: {item['tfidf_score']:.4f}")
            else:
                print("  (Not enough unique tokens for rare word analysis)")
        
        print("\n" + "="*80)
        print("NAMED ENTITIES")
        print("="*80)
        if 'named_entities' in results:
            ner = results['named_entities']
            print(f"Total entities found: {ner['total_entities']}")
            
            print(f"\nTop 5 Most Frequent Entities:")
            for entity, count in ner['top_entities']:
                print(f"  {entity}: {count} occurrences")
            
            print(f"\nEntity counts by type:")
            for entity_type, count in ner['entity_counts'].items():
                print(f"  {entity_type}: {count}")
            
            print(f"\nSample entities by type:")
            for entity_type, entities in ner['entities_by_type'].items():
                unique_entities = list(set(entities))[:5]
                print(f"  {entity_type}: {', '.join(unique_entities)}")
            
            print(f"\nPOS Tag Distribution (top 10):")
            sorted_pos = sorted(ner['pos_counts'].items(), key=lambda x: x[1], reverse=True)
            for tag, count in sorted_pos[:10]:
                print(f"  {tag}: {count}")
        
        # Print Flesch-Kincaid analysis if available
        if 'flesch_kincaid' in results:
            fk = results['flesch_kincaid']
            print("\n" + "="*80)
            print("FLESCH-KINCAID GRADE LEVEL ANALYSIS")
            print("="*80)
            print(f"Grade Level: {fk['flesch_kincaid_grade']} (requires ~{int(fk['flesch_kincaid_grade'])} years of education)")
            print(f"\nText Statistics:")
            print(f"  Total sentences: {fk['total_sentences']:,}")
            print(f"  Total words: {fk['total_words']:,}")
            print(f"  Total syllables: {fk['total_syllables']:,}")
            print(f"  Avg words per sentence: {fk['avg_words_per_sentence']}")
            print(f"  Avg syllables per word: {fk['avg_syllables_per_word']}")
            print(f"\nMost Complex Words (High Grade Level):")
            for item in fk['complex_words']:
                print(f"  {item['word']}: {item['syllables']} syllables, {item['length']} letters (complexity: {item['complexity_score']})")
        
    elif os.path.isdir(args.input):
        print(f"Processing directory: {args.input}")
        results = process_directory(args.input, top_n=args.top_n, pattern=args.pattern, max_chars=max_chars, enable_fk=args.flesch_kincaid)
        
        print(f"\nProcessed {len(results)} files")
        for result in results:
            print(f"\n{'='*80}")
            print(f"File: {result['filename']}")
            print(f"{'='*80}")
            if result.get('truncated'):
                print(f"Text length: {result['text_length']:,} characters (truncated from {result['original_length']:,})")
            else:
                print(f"Text length: {result['text_length']:,} characters")
            
            if 'tfidf' in result and 'top_tokens' in result['tfidf']:
                print(f"\nTop {args.top_n} TF-IDF tokens:")
                for item in result['tfidf']['top_tokens'][:5]:  # Show top 5
                    print(f"  {item['token']}: {item['tfidf_score']:.4f}")
                
                if 'rare_tokens' in result['tfidf'] and result['tfidf']['rare_tokens']:
                    print(f"\nRare vocabulary (difficult words):")
                    for item in result['tfidf']['rare_tokens'][:5]:  # Show 5 rare words
                        print(f"  {item['token']}: {item['tfidf_score']:.4f}")
            
            if 'named_entities' in result:
                ner = result['named_entities']
                print(f"\nEntities: {ner['total_entities']}")
                print(f"Entity types: {', '.join(ner['entity_counts'].keys())}")
            
            if 'flesch_kincaid' in result:
                fk = result['flesch_kincaid']
                print(f"\nFlesch-Kincaid Grade: {fk['flesch_kincaid_grade']}")
                print(f"Complex words: {', '.join([w['word'] for w in fk['complex_words'][:5]])}")
    else:
        print(f"Error: {args.input} is not a valid file or directory")
        return
    
    # Save to JSON if requested
    if args.output:
        import json
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
