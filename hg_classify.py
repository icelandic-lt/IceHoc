import argparse
import pickle
import re
import time

from transformers import AutoTokenizer, AutoModel
import torch

homographs = ["palli", "villa", "kalli", "galli", "galla", "gallar", "göllum", "gallinn", "gallann", "gallanum",
              "gallans", "gallarnir", "gallana", "göllunum", "gallanna", "gulli", "halli", "ella", "elli", "holl",
              "hollum", "bollum", "palla", "villu", "polli", "malla", "bolla", "kalla", "kolla", "pollar", "polla",
              "kollu", "dalla", "halla", "bollunum", "villi", "ullar", "villunni", "ollu", "grilla", "villan", "gellur",
              "lalla", "villuna", "holli", "holla", "böll", "gullu", "malli", "pollum", "pollinn", "dill", "villum",
              "pollarnir", "villur", "pollana", "villunnar", "alla", "drolla", "mallar", "dillum", "grilli", "villurnar",
              "villunum", "milli", "grillir", "lalli", "gulla", "gella"]


def find_homograph_positions_in_context(context, homograph, tokenizer, device):
    """
    Tokenizes the context, identifies the positions of the homograph tokens,
    and generates embeddings for classification.
    """
    encoded = tokenizer(context, return_tensors='pt', padding='max_length', truncation=True, max_length=512)
    input_ids = encoded['input_ids'].to(device)
    attention_mask = encoded['attention_mask'].to(device)

    # Find homograph tokens and their IDs
    homograph_tokens = tokenizer.tokenize(homograph)
    homograph_ids = tokenizer.convert_tokens_to_ids(homograph_tokens)

    # Identify positions of homograph tokens
    positions = [i for i, token_id in enumerate(input_ids[0]) if token_id in homograph_ids]

    return input_ids, attention_mask, positions


def get_context_around_homograph(sentence, homograph, around):
    """
    Extracts the context around the homograph within the sentence based on the --around parameter.
    """
    # If --around is not used, return the sentence as it is.
    if around is None:
        return sentence

    words = sentence.split()
    for i, word in enumerate(words):
        # Find homograph in sentence.
        if word.strip(",.?!") == homograph:
            start_index = max(i - around, 0)
            end_index = min(i + around + 1, len(words))
            return " ".join(words[start_index:end_index])
    # Return original sentence if homograph isn't found or --around is 0.
    return sentence


def generate_combined_embeddings_for_classification(input_ids, attention_mask, positions, model):
    with torch.no_grad():
        outputs = model(input_ids, attention_mask=attention_mask)
    sequence_output = outputs.last_hidden_state

    # [CLS] token embedding
    cls_embedding = sequence_output[:, 0, :]

    if positions:
        homograph_embedding = torch.mean(sequence_output[:, positions, :], dim=1)
    else:
        print("Homograph positions not found, using [CLS] embedding as a placeholder.")
        homograph_embedding = cls_embedding

    combined_embedding = torch.cat((cls_embedding, homograph_embedding), dim=1).squeeze(0).cpu().numpy()
    return combined_embedding.reshape(1, -1)


def classify_sentence_homographs(sentence, homographs, tokenizer, model, classifier, device, around):
    homograph_regex = '|'.join([f"(\\b{homograph}\\b)" for homograph in homographs])
    predictions = []

    for match in re.finditer(homograph_regex, sentence, re.IGNORECASE):
        homograph = match.group()
        context = get_context_around_homograph(sentence, homograph, around)
        input_ids, attention_mask, positions = find_homograph_positions_in_context(context, homograph, tokenizer, device)
        combined_embedding = generate_combined_embeddings_for_classification(input_ids, attention_mask, positions, model)
        prediction = classifier.predict(combined_embedding)
        predictions.append((homograph, prediction[0]))

    return predictions


def load_model_and_tokenizer(model, classifier_path, device):
    if model == 'distilbert':
        print("Loading DistilBERT model ...")
        tokenizer = AutoTokenizer.from_pretrained('distilbert-base-uncased')
        model = AutoModel.from_pretrained('distilbert-base-uncased').to(device)
    elif model == 'sbert-ruquad':
        print("Loading sbert-ruquad model ...")
        tokenizer = AutoTokenizer.from_pretrained('language-and-voice-lab/sbert-ruquad')
        model = AutoModel.from_pretrained('language-and-voice-lab/sbert-ruquad').to(device)
    elif model == 'labse':
        print("Loading LaBSE model ...")
        tokenizer = AutoTokenizer.from_pretrained('setu4993/LaBSE')
        model = AutoModel.from_pretrained('setu4993/LaBSE').to(device)
    elif model == 'icelandic-ner-bert':
        print("Loading icelandic-ner-bert model ...")
        tokenizer = AutoTokenizer.from_pretrained('grammatek/icelandic-ner-bert')
        model = AutoModel.from_pretrained('grammatek/icelandic-ner-bert').to(device)
    elif model == 'convbert':
        print("Loading convbert-base-igc-is model ...")
        tokenizer = AutoTokenizer.from_pretrained('jonfd/convbert-base-igc-is')
        model = AutoModel.from_pretrained('jonfd/convbert-base-igc-is').to(device)
    else:
        print(f"Unsupported model {model}")
        exit(1)

    with open(classifier_path, 'rb') as f:
        classifier = pickle.load(f)

    return tokenizer, model, classifier


def main():
    parser = argparse.ArgumentParser(description='Inference using saved model and transformer model.')
    parser.add_argument("--model", type=str,
                        choices=["distilbert", "sbert-ruquad", "labse", "icelandic-ner-bert", "convbert"],
                        required=True, help="Model type to use")
    parser.add_argument('--classifier', type=str, required=True,
                        help='Path to the homograph logistic regression classifier.')
    parser.add_argument('-s', '--sentence', type=str, help='Individual sentence for inference.')
    parser.add_argument('--file', type=str, help='Path to the file containing sentences for inference.')
    parser.add_argument("--gpu", action="store_true", help="Use GPU for training if available")
    parser.add_argument('--around', type=int, help='Number of words around the homograph to consider for context.',
                        default=None)
    args = parser.parse_args()

    # If GPU flag is set and torch sees a GPU, set device to cuda
    device = torch.device("cuda" if args.gpu and torch.cuda.is_available() else "cpu")
    tokenizer, model, classifier = load_model_and_tokenizer(args.model, args.classifier, device)

    if args.sentence:
        start_time = time.time()
        predictions = classify_sentence_homographs(args.sentence, homographs, tokenizer, model, classifier, device,
                                                   args.around)
        for homograph, prediction in predictions:
            print(f"Prediction for '{homograph}': {prediction}")
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Time taken for processing: {elapsed_time:.6f} seconds")
    elif args.file:
        with open(args.file, 'r') as file:
            lines = file.readlines()
            start_time = time.time()
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                predictions = classify_sentence_homographs(line, homographs, tokenizer, model, classifier, device,
                                                           args.around)
                if predictions:
                    for homograph, prediction in predictions:
                        print(f"'{line}', Homograph: '{homograph}', Prediction: {prediction}")
                else:
                    print(f"No specified homographs found in: '{line}'")

            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"Time taken for processing: {elapsed_time:.6f} seconds")
    else:
        print("Please provide either a sentence using -s or a file path using --file.")


if __name__ == "__main__":
    main()