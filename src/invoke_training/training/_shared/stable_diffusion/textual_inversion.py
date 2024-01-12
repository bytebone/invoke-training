import torch
from transformers import CLIPTextModel, CLIPTokenizer, PreTrainedTokenizer


def add_tokens_to_tokenizer(placeholder_tokens: list[str], tokenizer: PreTrainedTokenizer):
    """Add new tokens to a tokenizer.

    Raises:
        ValueError: Raises if the tokenizer already contains one of the tokens in `placeholder_tokens`.
    """
    num_added_tokens = tokenizer.add_tokens(placeholder_tokens)
    if num_added_tokens != len(placeholder_tokens):
        raise ValueError(
            f"The tokenizer already contains one of the tokens in '{placeholder_tokens}'. Please pass a different"
            " 'placeholder_token' that is not already in the tokenizer."
        )


def initialize_placeholder_tokens_from_initializer_token(
    tokenizer: CLIPTokenizer, text_encoder: CLIPTextModel, initializer_token: str, placeholder_tokens: list[str]
) -> list[int]:
    # Convert the initializer_token and placeholder_token to token ids.
    initializer_token_ids = tokenizer.encode(initializer_token, add_special_tokens=False)
    if len(initializer_token_ids) > 1:
        raise ValueError(
            f"The initializer_token '{initializer_token}' gets tokenized to {len(initializer_token_ids)} tokens."
            " Choose a different initializer that maps to a single token."
        )
    initializer_token_id = initializer_token_ids[0]
    placeholder_token_ids = tokenizer.convert_tokens_to_ids(placeholder_tokens)

    # convert_tokens_to_ids returns a `int | list[int]` type, but since we pass in a list it should always return a
    # list.
    assert isinstance(placeholder_token_ids, list)

    # Initialize the newly-added placeholder token(s) with the embeddings of the initializer token.
    token_embeds = text_encoder.get_input_embeddings().weight.data
    with torch.no_grad():
        for token_id in placeholder_token_ids:
            token_embeds[token_id] = token_embeds[initializer_token_id].clone()

    return placeholder_token_ids
