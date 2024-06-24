import math
from typing import List, Optional, Tuple, Union

import torch
import torch.utils.checkpoint
from torch import nn
from torch.nn import BCEWithLogitsLoss, CrossEntropyLoss, MSELoss

import numpy as np

import os
import torch
import torch.nn as nn
import timm
from timm.models.layers import to_2tuple, trunc_normal_, DropPath
from timm.models.vision_transformer import Attention, Mlp, PatchEmbed, Block
from pos_embed import get_2d_sincos_pos_embed

class PatchEmbed(nn.Module):
    def __init__(self, img_size=224, patch_size=16, in_chans=3, embed_dim=768):
        super().__init__()

        img_size = to_2tuple(img_size)
        patch_size = to_2tuple(patch_size)
        num_patches = (img_size[1] // patch_size[1]) * (img_size[0] // patch_size[0])
        self.img_size = img_size
        self.patch_size = patch_size
        self.num_patches = num_patches

        self.proj = nn.Conv2d(in_chans, embed_dim, kernel_size=patch_size, stride=patch_size)

    def forward(self, x):
        #print("patch embed:",x.shape)
        if torch.isnan(x).any():
                    print("NaN detected before convo")
        if torch.isinf(x).any():
            print("Infinite values detected before convolution")
        #print("before convo:", x)
        
        x = self.proj(x).flatten(2).transpose(1, 2)
        return x
"""
class Block(nn.Module):
    def __init__(self, dim, num_heads, mlp_ratio=4., qkv_bias=False, qk_scale=None, drop=0., attn_drop=0.,
                 drop_path=0., act_layer=nn.GELU, norm_layer=nn.LayerNorm):
        super().__init__()
        self.norm1 = norm_layer(dim)
        self.norm1_a = norm_layer(dim)
        self.norm1_v = norm_layer(dim)
        self.attn = Attention(
            dim, num_heads=num_heads, qkv_bias=qkv_bias, qk_scale=qk_scale, attn_drop=attn_drop, proj_drop=drop)
        # NOTE: drop path for stochastic depth, we shall see if this is better than dropout here
        self.drop_path = DropPath(drop_path) if drop_path > 0. else nn.Identity()
        self.norm2 = norm_layer(dim)
        self.norm2_a = norm_layer(dim)
        self.norm2_v = norm_layer(dim)
        mlp_hidden_dim = int(dim * mlp_ratio)
        self.mlp = Mlp(in_features=dim, hidden_features=mlp_hidden_dim, act_layer=act_layer, drop=drop)

    def forward(self, x, modality=None):
        if modality == None:
            x = x + self.drop_path(self.attn(self.norm1(x)))
            x = x + self.drop_path(self.mlp(self.norm2(x)))
        elif modality == 'a':
            x = x + self.drop_path(self.attn(self.norm1_a(x)))
            x = x + self.drop_path(self.mlp(self.norm2_a(x)))
        elif modality == 'v':
            x = x + self.drop_path(self.attn(self.norm1_v(x)))
            x = x + self.drop_path(self.mlp(self.norm2_v(x)))

        # this is a workaround to avoid ddp complain
        x = x + 0.0 * (self.norm1(x) + self.norm2(x) + self.norm1_a(x) + self.norm2_a(x) + self.norm1_v(x) + self.norm2_v(x))
        return x
"""
class Block(nn.Module):
    def __init__(self, dim, num_heads, mlp_ratio=4., qkv_bias=False, qk_scale=None, drop=0., attn_drop=0.,
                 drop_path=0., act_layer=nn.GELU, norm_layer=nn.LayerNorm):
        super().__init__()
        self.norm1 = norm_layer(dim)
        self.norm1_a = norm_layer(dim)
        self.norm1_v = norm_layer(dim)
        self.attn = Attention(
            dim, num_heads=num_heads, qkv_bias=qkv_bias, qk_scale=qk_scale, attn_drop=attn_drop, proj_drop=drop)
        # NOTE: drop path for stochastic depth, we shall see if this is better than dropout here
        self.drop_path = DropPath(drop_path) if drop_path > 0. else nn.Identity()
        self.norm2 = norm_layer(dim)
        self.norm2_a = norm_layer(dim)
        self.norm2_v = norm_layer(dim)
        mlp_hidden_dim = int(dim * mlp_ratio)
        self.mlp = Mlp(in_features=dim, hidden_features=mlp_hidden_dim, act_layer=act_layer, drop=drop)
    def forward(self, x, modality=None):

            original_x = x
            if modality is None:
                x = self.norm1(x)
                if torch.isnan(x).any():
                    print("NaN detected after norm1")
                x = x + self.drop_path(self.attn(x))
                if torch.isnan(x).any():
                    print("NaN detected after attn")
                x = self.norm2(x)
                if torch.isnan(x).any():
                    print("NaN detected after norm2")
                x = x + self.drop_path(self.mlp(x))
                if torch.isnan(x).any():
                    print("NaN detected after mlp")
            elif modality == 'a':
                x = self.norm1_a(x)
                x = x + self.drop_path(self.attn(x))
                x = self.norm2_a(x)
                x = x + self.drop_path(self.mlp(x))
            elif modality == 'v':
                x = self.norm1_v(x)
                x = x + self.drop_path(self.attn(x))
                x = self.norm2_v(x)
                x = x + self.drop_path(self.mlp(x))
    
            # Additional workaround to avoid ddp complain might not be necessary unless using ddp and seeing issues.
            x = x + 0.0 * (original_x + self.norm1(original_x) + self.norm2(original_x) + 
                           self.norm1_a(original_x) + self.norm2_a(original_x) + 
                           self.norm1_v(original_x) + self.norm2_v(original_x))
            return x
        
# the finetuned CAV-MAE model
class CAVMAEFTAudio(nn.Module):
    def __init__(self, img_size=224, audio_length=1024, patch_size=16, in_chans=3,
                 embed_dim=768, modality_specific_depth=11, num_heads=12, mlp_ratio=4., norm_layer=nn.LayerNorm, norm_pix_loss=False, tr_pos=True):
        super().__init__()
        timm.models.vision_transformer.Block = Block

        timm.models.vision_transformer.PatchEmbed = PatchEmbed
        timm.models.vision_transformer.Block = Block

        self.patch_embed_a = PatchEmbed(img_size, patch_size, 1, embed_dim)

        self.patch_embed_a.num_patches = int(audio_length * 128 / 256)

        self.modality_a = nn.Parameter(torch.zeros(1, 1, embed_dim))

        self.pos_embed_a = nn.Parameter(torch.zeros(1, self.patch_embed_a.num_patches, embed_dim), requires_grad=tr_pos)  # fixed sin-cos embedding

        self.blocks_a = nn.ModuleList([Block(embed_dim, num_heads, mlp_ratio, qkv_bias=True, qk_scale=None, norm_layer=norm_layer) for i in range(modality_specific_depth)])
        self.blocks_u = nn.ModuleList([Block(embed_dim, num_heads, mlp_ratio, qkv_bias=True, qk_scale=None, norm_layer=norm_layer) for i in range(12 - modality_specific_depth)])

        self.norm_a = norm_layer(embed_dim)

        self.initialize_weights()

    def get_patch_num(self, input_shape, stride):
        test_input = torch.zeros(1, 1, input_shape[0], input_shape[1])
        test_proj = torch.nn.Conv2d(1, 4, kernel_size=(16, 16), stride=(stride, stride))
        test_output = test_proj(test_input)
        return test_output.shape[2], test_output[3], test_output[2] * test_output[2]

    def initialize_weights(self):
        pos_embed_a = get_2d_sincos_pos_embed(self.pos_embed_a.shape[-1], 8, int(self.patch_embed_a.num_patches/8), cls_token=False)
        self.pos_embed_a.data.copy_(torch.from_numpy(pos_embed_a).float().unsqueeze(0))

        w = self.patch_embed_a.proj.weight.data
        torch.nn.init.xavier_uniform_(w.view([w.shape[0], -1]))

        torch.nn.init.normal_(self.modality_a, std=.02)

        self.apply(self._init_weights)

    def _init_weights(self, m):
        if isinstance(m, nn.Linear):
            # we use xavier_uniform following official JAX ViT:
            torch.nn.init.xavier_uniform_(m.weight)
            if isinstance(m, nn.Linear) and m.bias is not None:
                nn.init.constant_(m.bias, 0)
        elif isinstance(m, nn.LayerNorm):
            nn.init.constant_(m.bias, 0)
            nn.init.constant_(m.weight, 1.0)

    def forward(self, a):
        #print("from CAVE inside:", a)
        #print("shape before CAVE:", a.shape)
        # expect input [b, t, f]
        a = a.unsqueeze(1)
        a = a.transpose(2, 3)
        #print("from CAVE before patch:",a)
        a = self.patch_embed_a(a)
        #print("from CAVE after patch:",a)
        a = a + self.pos_embed_a
        a = a + self.modality_a
        #print("from CAVE inside 2:", a)
        #print("shape before putting in block:",a.shape)
        for blk in self.blocks_a:
            a = blk(a)

        for blk in self.blocks_u:
            a = blk(a, 'a')

        #print("from CAVE inside 3:", a)
        a = self.norm_a(a)
        # output in shape [b, t, dim]
        #print("from CAVE inside 4:", a)
        return a