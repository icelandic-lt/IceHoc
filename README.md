# Icelandic homograph classification (IceHoc)

This project implements the classification of Icelandic homographs in a manner similar to that described in:

`Nicolis, M., Klimkov, V. (2021) Homograph disambiguation with contextual word embeddings for TTS systems. Proc. 11th
ISCA Speech Synthesis Workshop (SSW 11), 222-226, doi: 10.21437/SSW.2021-39`, utilizing contextual word embeddings.

However, it introduces some distinct modifications:

We employ logistic regression on embeddings produced by a transformer model to classify homographs. In line with the
suggestions from the referenced paper, we use the **CLS** token embedding. Additionally, we incorporate the homograph
word embedding itself as input features for the classifier. Moreover, we focus only on a specific "area" of tokens
surrounding the homograph. This is configurable for training via the `--around` parameter.

Using this approach, we achieve state-of-the-art results in homograph classification for Icelandic when combined with
the **ConvBert** or **LaBSE** models.

## Transformer models

The following transformer models were initially examined for generation of the embeddings:

- [distilbert-base-uncased](https://huggingface.co/bert-base-multilingual-cased)
- [icebert](https://huggingface.co/mideind/IceBERT)
- [icebert-large](https://huggingface.co/mideind/IceBERT-large)
- [icelandic-ner-bert](https://huggingface.co/grammatek/icelandic-ner-bert)
- [labse](https://huggingface.co/setu4993/LaBSE)
- [macocu-is](https://huggingface.co/MaCoCu/XLMR-MaCoCu-is)
- [macocu-base-is](https://huggingface.co/MaCoCu/XLMR-base-MaCoCu-is)
- [sbert-ruquad](https://huggingface.co/language-and-voice-lab/sbert-ruquad)
- [convbert-is](https://huggingface.co/jonfd/convbert-base-igc-is)

Due to our reliance on a Wordpiece Tokenizer, the RoBERTa-based models `macocu-is`, `macocu-base-is`, `IceBert`, and
`IceBert-large` are not suitable for generating homograph embeddings, as they utilize a BPE (Byte Pair Encoding)
Tokenizer. Consequently, these models were evaluated solely on their performance using CLS-token embeddings for
classification, which, according to our experiments, is not adequate.
However, it's likely that these models would perform exceptionally well if a method for identifying word embeddings
were developed for BPE-based tokenizers.

## Training set, Training approach and performance measurement

We are using a manually labelled dataset with 63 homograph word forms, generated from the Icelandic Gigaword Corpus
(IGC). The training set is made up of CSV files with 2 columns: a sentence from the IGC containing the homograph marked
via `[[<homograph>]]` and a manually attached label `0`/`1` according to the 2 possible pronunciations of the homograph,
separated by comma. The training set can be retrieved via
[Google Drive](https://drive.google.com/drive/u/1/folders/1MIlq9RVlvuCB70K8nsHJNcLGGXlQqKeO)

This dataset is highly unbalanced. Therefore, training is done only on the same amount of `1` labels as there are `0`
labels by sampling the same amount of labels. This reduced dataset is split 8-1-1 into train/validation/test set.

All training code can be found in the file [hg_train.py](hg_train.py). The dataset is prepared according to the given
`--around` parameter, then tokenized, embeddings are generated via the given BERT model from the tokenized text and
finally the CLS and homograph word embeddings are isolated to build combined classification features.

As tokenization takes a lot of time, the results are cached into a file alongside the dataset directory, which is
automatically loaded if it exists at training start. This file's name contains the BERT model name as well as the given
value for `--around` for taking into account the distinct parameters. If you don't want to load this cached file and
instead want the training script to recalculate the tokens, add `--force` as a parameter to the training script.

For the classification process, the following parameters can be set. The defaults are shown in parentheses and have
proven to give good results:

- `N_EPOCHS` (50)
- `BATCH_SIZE` (512)
- `ALPHA` (0.001)
- `TEST_SIZE` (0.1)
- `VALIDATION_SIZE` (0.1)

The F1 score is calculated at the end for the complete test set. If you specify the parameter `--histogram` F1 scores
for each homograph individually are also calculated. 

The training needs around 16GB VRAM memory on a GPU, additionally to the transformer model usage. Training on CPU is
possible but prohibitively slow (with 32 cores - 20x slower than 1 GPU), because of the BERT embeddings generation.
Training of the classifier itself with the pre-generated data is done on CPU and very fast.

## Classifier model

We use SKlearn [SGDClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.SGDClassifier.html)
with the loss function `loss='log_loss'`, i.e. logistic regression. The classifier is saved as a pickle file and the
resulting model file size is just ~7KB. Of course, one always needs additionally the corresponding BERT model for
inference as well.

## Performance

The embeddings generated by the BERT models have proven to make a big difference for the performance of the
classifier. The choice of the right transformer model influences the outcome much more than adjusting the context size
around the homograph from e.g. 5 to 12 or simple hyperparameter tunings.

The model `distilbert-base-uncased` was used as a reference point for a model that has probably not seen any Icelandic
text, to get a feeling for a low baseline.

Besides `LaBSE`, which is a multilingual model and `Macocu-IS`, which was fine-tuned from Multi Lingual
`XLM-RoBERTa-Large`, the other transformer models were specifically targeted for Icelandic.

These are the results for just using the CLS token embeddings as classifier input:

| Model                   | F1 Score | --around |
|-------------------------|----------|----------|
| distilbert-base-uncased | 0.67     | 8        |
| ConvBert                | 0.79     | 8        |
| LaBSE                   | **0.85** | 8        |
| IceBert                 | 0.80     | 8        |
| Macocu-is               | 0.82     | 8        |
| sbert-ruquad            | 0.76     | 8        |
| Icelandic-ner-bert      | 0.78     | 8        |

The results above were retrieved via an older version of our training script and are not integrated into this
repository. As can be seen, the BERT models LaBSE and Macocu-IS score top, whereas the specialized Icelandic BERT models
fall behind. These would be the final results, if we'd just implemented the procedures of the cited paper.

By adding the homograph embeddings to the classifier's input features, the following results are obtained:

| Model                   | F1 Score  | --around |
|-------------------------|-----------|----------|
| distilbert-base-uncased | 0.754     | 8        |
| ConvBert                | **0.950** | 10       |
| ConvBert                | *0.942*   | 8        |
| LaBSE                   | *0.935*   | 8        |
| sbert-ruquad            | 0.865     | 8        |
| Icelandic-ner-bert      | 0.889     | 8        |

The outcomes exhibit a significant improvement across _all_ BERT model variants. Notably, ConvBert demonstrates a
remarkable enhancement, with its F1 score increasing by `0.16`. This substantial increase underscores its enhanced capacity
for generating meaningful word embeddings, solidifying its position as a robust model for natural language processing
tasks in Icelandic. Additionally, LaBSE proves to be a solid choice for multilingual purposes, including Icelandic text
classification, due to its robust performance across many languages.

## Model training

### Prerequisites

Install all dependencies via

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Training

For training of the classifier, the Python script `hg_train.py` is used. It can be run with the following command line

```bash
mkdir -p classifer/   # directory is not yet automatically created
python3 hg_train.py --directory training_data/ --model convbert --gpu --around 10
```

The parameter values for training script stand for:

- directory with training data in path `training_data/`
- transformer model: `convbert`
- use GPU
- word context size: `10` tokens (counted via String split !) left and right from the found homograph. The token number
  might be less per direction in case the available number of tokens is less

After training is finished, you can find the classifier model inside the directory `classifier`, e.g.
`classifier/trained_clf_convbert_10_0.950.pkl`

## Model inference

To inference the trained classifier, use the Python script `hg_classify.py`. Please remember to always combine the
correct classifier trained with the specific BERT model !

```bash
python3 hg_classify.py --model convbert --classifier classifier/trained_clf_convbert_10_0.950.pkl -s "Þeir \
     náttúrulega voru í góðum málum , þeir voru búnir að galla sig upp og voru tilbúnir "
```

You can als add the parameter `--gpu` to let it run on your GPU, if available. Via passing the parameter `--file`, you
can classify each line of a file. Results are printed on `stdout`.

# Copyright, Citation

Copyright (C) 2024, Grammatek ehf, licensed via the [APACHE License v2](LICENSE)

If you base any of your research or software on this repository, please consider citing.

```
@misc{IceHoc,
	author={D. Schnell, A.B. Nikulásdóttir},
	title={IceHoc},
	year={2024},
	url={https://www.github.com/grammatek/IceHoc},
}
```