# laya fine-tune script (vendored)

Nguồn: `NandhaKishorM/laya` @ `notebooks/laya_finetune_typed_decisions_mps.py` (Apache-2.0),
tải 2026-10-04. Chạy được cả CPU (`--device cpu`).

Vì sao vendor: chromly fine-tune trên dataset riêng (`store/s1/ft/train_items.pt`) — script
nhận items.pt local bất kỳ (cache "legacy without metadata" được dùng nguyên trạng), không cần
dataset HF của họ. Sửa đổi (nếu có) ghi rõ trong file này.

Cách dùng (qua chromly): `chromly s1 finetune --epochs 2` — wrapper build items + gọi script.
