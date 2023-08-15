import typing

import torch
from torch.utils.data import DataLoader
from transformers import PreTrainedTokenizer

from invoke_training.training.finetune_lora.finetune_lora_config import DatasetConfig
from invoke_training.training.shared.data.datasets.hf_dir_image_caption_dataset import (
    HFDirImageCaptionDataset,
)
from invoke_training.training.shared.data.datasets.hf_hub_image_caption_dataset import (
    HFHubImageCaptionDataset,
)
from invoke_training.training.shared.data.datasets.transform_dataset import (
    TransformDataset,
)
from invoke_training.training.shared.data.transforms.load_cache_transform import (
    LoadCacheTransform,
)
from invoke_training.training.shared.data.transforms.sd_tokenize_transform import (
    SDTokenizeTransform,
)
from invoke_training.training.shared.data.transforms.sdxl_image_transform import (
    SDXLImageTransform,
)
from invoke_training.training.shared.data.transforms.tensor_disk_cache import (
    TensorDiskCache,
)


def _collate_fn(examples):
    """A batch collation function for the image-caption SDXL data loader."""
    out_examples = {
        "image": torch.stack([example["image"] for example in examples]),
        "id": [example["id"] for example in examples],
        "original_size_hw": [example["original_size_hw"] for example in examples],
        "crop_top_left_yx": [example["crop_top_left_yx"] for example in examples],
    }

    if "caption_token_ids_1" in examples[0]:
        out_examples["caption_token_ids_1"] = torch.stack([example["caption_token_ids_1"] for example in examples])
        out_examples["caption_token_ids_2"] = torch.stack([example["caption_token_ids_2"] for example in examples])

    if "text_encoder_output" in examples[0]:
        out_examples["text_encoder_output"] = {
            "prompt_embeds": torch.stack([example["text_encoder_output"]["prompt_embeds"] for example in examples]),
            "pooled_prompt_embeds": torch.stack(
                [example["text_encoder_output"]["pooled_prompt_embeds"] for example in examples]
            ),
        }

    return out_examples


def build_image_caption_sdxl_dataloader(
    config: DatasetConfig,
    tokenizer_1: PreTrainedTokenizer,
    tokenizer_2: PreTrainedTokenizer,
    batch_size: int,
    text_encoder_output_cache_dir: typing.Optional[str] = None,
    shuffle: bool = True,
) -> DataLoader:
    """Construct a DataLoader for an image-caption dataset for Stable Diffusion XL.

    Args:
        config (DatasetConfig): The dataset config.
        tokenizer (CLIPTokenizer): The tokenizer to apply to the captions. Can be None if
            `text_encoder_output_cache_dir` is set.
        batch_size (int): The DataLoader batch size.
        text_encoder_output_cache_dir (str, optional): The directory where text encoder outputs are cached and should be
            loaded from. If set, then the TokenizeTransform will not be applied.
        shuffle (bool, optional): Whether to shuffle the dataset order.
    Returns:
        DataLoader
    """
    if config.dataset_name is not None:
        base_dataset = HFHubImageCaptionDataset(
            dataset_name=config.dataset_name,
            hf_load_dataset_kwargs={
                "name": config.dataset_config_name,
                "cache_dir": config.hf_cache_dir,
            },
            image_column=config.image_column,
            caption_column=config.caption_column,
        )
    elif config.dataset_dir is not None:
        base_dataset = HFDirImageCaptionDataset(
            dataset_dir=config.dataset_dir,
            hf_load_dataset_kwargs=None,
            image_column=config.image_column,
            caption_column=config.caption_column,
        )
    else:
        raise ValueError("One of 'dataset_name' or 'dataset_dir' must be set.")

    all_transforms = []
    all_transforms.append(
        SDXLImageTransform(resolution=config.resolution, center_crop=config.center_crop, random_flip=config.random_flip)
    )

    if text_encoder_output_cache_dir is None:
        all_transforms.append(
            SDTokenizeTransform(tokenizer_1, src_caption_key="caption", dst_token_key="caption_token_ids_1")
        )
        all_transforms.append(
            SDTokenizeTransform(tokenizer_2, src_caption_key="caption", dst_token_key="caption_token_ids_2")
        )
    else:
        cache = TensorDiskCache(text_encoder_output_cache_dir)
        all_transforms.append(LoadCacheTransform(cache=cache, cache_key_field="id", output_field="text_encoder_output"))

    dataset = TransformDataset(base_dataset, all_transforms)

    return DataLoader(
        dataset,
        shuffle=shuffle,
        collate_fn=_collate_fn,
        batch_size=batch_size,
        num_workers=config.dataloader_num_workers,
    )
