#!/usr/bin/env python3
"""Generate the first 20 deterministic PyTorch/UAST seed cases."""

import argparse
from pathlib import Path


CASES = [
    ("DL001", "tensor_literal", "result = torch.tensor([[1.0, -2.0, 3.0], [4.0, 0.0, -1.0]], dtype=torch.float32)"),
    ("DL002", "zeros", "result = torch.zeros((2, 3), dtype=torch.float32)"),
    ("DL003", "ones", "result = torch.ones((2, 3), dtype=torch.float32)"),
    ("DL004", "arange", "result = torch.arange(0, 6, dtype=torch.float32)"),
    ("DL005", "reshape", "result = torch.arange(0, 6, dtype=torch.float32).reshape(2, 3)"),
    ("DL006", "transpose", "result = torch.tensor([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]).transpose(0, 1)"),
    ("DL007", "unsqueeze_squeeze", "result = torch.tensor([1.0, 2.0, 3.0]).unsqueeze(0).squeeze(0)"),
    ("DL008", "concat", "result = torch.cat([torch.tensor([1.0, 2.0]), torch.tensor([3.0, 4.0])], dim=0)"),
    ("DL009", "stack", "result = torch.stack([torch.tensor([1.0, 2.0]), torch.tensor([3.0, 4.0])], dim=0)"),
    ("DL010", "slice_index", "result = torch.tensor([0.0, 1.0, 2.0, 3.0, 4.0])[1:4]"),
    ("DL011", "add_same_shape", "result = torch.tensor([1.0, 2.0]) + torch.tensor([3.0, 4.0])"),
    ("DL012", "add_broadcast", "result = torch.tensor([[1.0, 2.0], [3.0, 4.0]]) + torch.tensor([10.0, 20.0])"),
    ("DL013", "subtract", "result = torch.tensor([5.0, 7.0]) - torch.tensor([2.0, 3.0])"),
    ("DL014", "multiply", "result = torch.tensor([2.0, 3.0]) * torch.tensor([4.0, 5.0])"),
    ("DL015", "divide", "result = torch.tensor([8.0, 9.0]) / torch.tensor([2.0, 3.0])"),
    ("DL016", "matmul_2d", "result = torch.matmul(torch.tensor([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]), torch.tensor([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]))"),
    ("DL017", "sum", "result = torch.tensor([[1.0, 2.0], [3.0, 4.0]]).sum(dim=1)"),
    ("DL018", "mean", "result = torch.tensor([[1.0, 2.0], [3.0, 4.0]]).mean(dim=0)"),
    ("DL019", "relu", "result = torch.relu(torch.tensor([-2.0, -0.5, 0.0, 1.5]))"),
    ("DL020", "softmax", "result = torch.softmax(torch.tensor([1.0, 2.0, 3.0]), dim=0)"),
]

TEMPLATE = '''import json
import torch

CASE_ID = {case_id!r}
torch.manual_seed(20260911)

def encode(value):
    if isinstance(value, torch.Tensor):
        return {{
            "kind": "tensor",
            "shape": list(value.shape),
            "dtype": str(value.dtype),
            "device": str(value.device),
            "values": value.detach().cpu().tolist(),
        }}
    return value

{operation}

print(json.dumps({{"case": CASE_ID, "result": encode(result)}}, sort_keys=True))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        default="workstreams/dl-cross-language-research/fixtures/generated/dl-uast-seed",
    )
    args = parser.parse_args()
    root = Path(args.out_dir)
    root.mkdir(parents=True, exist_ok=True)
    for case_id, name, operation in CASES:
        case_dir = root / f"{case_id}_{name}"
        case_dir.mkdir(exist_ok=True)
        (case_dir / "source.py").write_text(
            TEMPLATE.format(case_id=case_id, operation=operation) + "\n",
            encoding="utf-8",
        )
    print(f"generated {len(CASES)} cases under {root}")


if __name__ == "__main__":
    main()
