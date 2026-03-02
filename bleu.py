import sacrebleu

# Simulate VLM translation outputs vs your ground truth
# Ground truth (your annotation)
references = [
    ['Limited-time summon event now live'],
    ['Player HP: 1523'],
    ['Special skill cooldown: 3 turns'],
]

# GPT-4V outputs
hypotheses_gpt = [
    'Limited-time summon event currently live',    # close
    'Player HP: 1523',                            # perfect
    'Special attack cooldown: 3 rounds',          # different words, same meaning
]

# Qwen2-VL outputs
hypotheses_qwen = [
    'Exclusive gacha recruitment event active',   # semantically same, different words
    'HP 1523',                                    # missing 'Player'
    'Ultimate cooldown 3 turns',                  # different wording
]

# Compute BLEU — sacrebleu expects [hypothesis] and [[reference]]
bleu_gpt  = sacrebleu.corpus_bleu(hypotheses_gpt,  [r[0] for r in references])
bleu_qwen = sacrebleu.corpus_bleu(hypotheses_qwen, [r[0] for r in references])

print(f'GPT-4V BLEU:  {bleu_gpt.score:.1f}')
print(f'Qwen2-VL BLEU: {bleu_qwen.score:.1f}')
print()
print('Notice: Qwen scores lower even though meaning is often correct.')
print('This is BLEU\'s limitation — it penalizes valid paraphrases.')
