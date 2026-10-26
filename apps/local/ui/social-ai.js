'use strict';
const providerNames = {
  openrouter: 'OpenRouter',
  orcarouter: 'OrcaRouter',
  'ollama-local': 'Ollama（ローカル）',
  'ollama-cloud': 'Ollama（クラウド）',
};
const jobStates = {
  queued: '予約済み',
  running: '生成中',
  succeeded: '成功・内容未検証',
  failed: '失敗・自動再送なし',
};
const usd = (value) =>
  value === null || value === undefined
    ? '不明（予約額を維持）'
    : `$${(value / 1000000).toFixed(6)}`;
function numeric(value, name, min, max, step = '1') {
  return el('input', { type: 'number', name, value, min, max, step, required: '' });
}
function checkedField(text, input) {
  return el('label', { class: 'check-field' }, [input, el('span', { text })]);
}
function socialSource(id) {
  return state.social?.find((v) => v.feedId === id);
}
function initSocialAI() {
  renderSocialForm();
}
function renderSocialForm() {
  const root = $('#social-form-root');
  if (!root || !state.boot) return;
  const type = el('select', { name: 'type', 'aria-label': 'SNSの種類' }, [
    option('bluesky:search', 'Bluesky・キーワード'),
    option('mastodon:tag', 'Mastodon・ハッシュタグ'),
    option('mastodon:account', 'Mastodon・アカウント'),
  ]);
  const name = el('input', {
    name: 'title',
    required: '',
    maxlength: 120,
    placeholder: '調査する分野名',
    'aria-label': 'SNS調査名',
  });
  const target = el('input', {
    name: 'target',
    required: '',
    maxlength: 200,
    placeholder: '人工知能 lang:ja',
    'aria-label': 'SNSの検索条件',
  });
  const origin = el('input', {
    name: 'origin',
    type: 'url',
    placeholder: 'https://mastodon.social',
    'aria-label': 'Mastodonサーバー',
  });
  const originField = field('Mastodonサーバー', origin);
  originField.hidden = true;
  type.addEventListener('change', () => {
    const mastodon = type.value.startsWith('mastodon:');
    originField.hidden = !mastodon;
    origin.required = mastodon;
    if (!mastodon) origin.value = '';
    target.placeholder = type.value.endsWith(':tag')
      ? 'AI,機械学習（1〜3個）'
      : type.value.endsWith(':account')
        ? 'サーバー内のアカウント名'
        : '人工知能 lang:ja';
  });
  const folder = folderSelect();
  folder.name = 'folderId';
  const form = el('form', { id: 'social-source-form', class: 'settings-grid' }, [
    field('SNSの種類', type),
    field('SNS調査名', name),
    field('検索条件（公開情報をサービスへ送信します）', target),
    originField,
    field('フォルダー', folder),
    field('収集間隔（分）', numeric(30, 'interval', 15, 1440)),
    field('対象期間（時間）', numeric(24, 'windowHours', 1, 168)),
    el('div', { class: 'form-actions' }, [
      el('button', { class: 'primary', text: 'SNSを登録', type: 'submit' }),
    ]),
  ]);
  form.addEventListener(
    'submit',
    safe(async (event) => {
      event.preventDefault();
      const submit = $('button', form);
      submit.disabled = true;
      try {
        const data = Object.fromEntries(new FormData(form)),
          [provider, kind] = data.type.split(':');
        const id = await api.call('social.save', {
          provider,
          kind,
          title: data.title,
          target: data.target,
          origin: data.origin || '',
          folderId: Number(data.folderId),
          interval: Number(data.interval),
          windowHours: Number(data.windowHours),
        });
        await boot();
        toast('SNSを登録しました。今すぐ収集、または次の定期収集で取得します');
        await showSocial(id);
      } finally {
        submit.disabled = false;
      }
    }),
  );
  root.replaceChildren(
    el('p', {
      text: '公開投稿を収集し、反応数と関連タグを調べます。登録だけでは外部通信しません。',
    }),
    form,
  );
}
async function showSocial(id) {
  state.socialId = id;
  page('research');
  await renderSocialList();
}
async function renderSocialList() {
  const root = $('#social-results');
  const sources = await api.call('social.list');
  state.social = sources;
  if (!sources.length) {
    root.replaceChildren(
      el('p', {
        text: '「集める」でSNSを登録すると、ここで反応数・関連タグ・話題を確認できます。',
      }),
    );
    return;
  }
  if (!sources.some((v) => v.feedId === state.socialId)) state.socialId = sources[0].feedId;
  const select = el(
    'select',
    { 'aria-label': 'SNS調査を選択' },
    sources.map((v) =>
      option(
        v.feedId,
        state.boot.feeds.find((f) => f.id === v.feedId)?.title || v.target,
        v.feedId === state.socialId,
      ),
    ),
  );
  select.addEventListener(
    'change',
    safe(async () => {
      state.socialId = Number(select.value);
      await renderSocialList();
    }),
  );
  const detail = el('div', { id: 'social-detail' });
  root.replaceChildren(
    el('div', { class: 'button-row' }, [
      select,
      button('結果を再読み込み', renderSocialList, 'subtle'),
    ]),
    detail,
  );
  const data = await api.call('social.detail', { id: state.socialId });
  if (Number(select.value) !== state.socialId) return;
  const source = data.source,
    feed = state.boot.feeds.find((f) => f.id === source.feedId),
    latest = data.runs[0];
  detail.append(
    el('p', {
      class: 'social-definition',
      text: `${source.provider} / ${source.kind} · ${source.target} · ${source.interval}分間隔 · 過去${source.windowHours}時間${feed?.paused ? ' · 購読停止中' : ''}`,
    }),
  );
  detail.append(
    el('div', { class: 'button-row' }, [
      button(
        '今すぐ収集',
        async (event) => {
          event.target.disabled = true;
          try {
            const r = await api.call('social.refresh', { id: source.feedId });
            await boot();
            await renderSocialList();
            toast(r.errors.length ? r.errors.join('\n') : 'SNSを収集しました', !!r.errors.length);
          } finally {
            event.target.disabled = false;
          }
        },
        'primary',
      ),
      button('記事を読む', () => chooseFilter({ mode: 'all', feedId: source.feedId }), 'secondary'),
      button('収集・自動抽出を設定', () => editSocial(source), 'subtle'),
    ]),
  );
  if (feed?.lastError)
    detail.append(
      el('p', { class: 'danger', text: `最終エラー: ${feed.lastError}（前回成功結果を保持）` }),
    );
  if (source.aiError)
    detail.append(el('p', { class: 'danger', text: `自動抽出の予約: ${source.aiError}` }));
  if (!latest) {
    detail.append(el('p', { text: 'まだ成功した収集結果がありません。' }));
    return;
  }
  const runSelect = el(
    'select',
    { 'aria-label': 'SNS収集履歴' },
    data.runs.map((r) =>
      option(r.id, `${date(r.collected)} · ${r.snapshot.sampleCount}投稿`, r.id === latest.id),
    ),
  );
  const snapshot = el('div');
  const draw = (run) => {
    snapshot.replaceChildren(
      el('p', {
        text: `収集サンプル内の順位です。いいね + 再投稿×2 + 返信。網羅性やSNS間の順位比較は保証しません。`,
      }),
    );
    const tags = el(
      'div',
      { class: 'tag-list' },
      run.snapshot.tags.map((t) => el('span', { text: `#${t.tag} · ${t.posts}` })),
    );
    snapshot.append(tags);
    for (const p of run.snapshot.posts)
      snapshot.append(
        el('div', { class: 'social-post' }, [
          el('strong', { class: 'score', text: p.score }),
          el('div', {}, [
            button(
              p.title,
              async () => {
                await chooseFilter({ mode: 'all', feedId: source.feedId });
                await openArticle(p.articleId);
              },
              'article-link',
            ),
            el('small', {
              text: `♥ ${p.likes} · 再投稿 ${p.reposts} · 返信 ${p.replies} · ${date(p.published)}`,
            }),
          ]),
        ]),
      );
  };
  runSelect.addEventListener('change', () =>
    draw(data.runs.find((r) => r.id === Number(runSelect.value))),
  );
  detail.append(field('収集履歴（直近30回）', runSelect), snapshot);
  draw(latest);
  const analysis = el('section', { class: 'case-section' }, [
    el('h3', { text: '重要トピック・AI解析' }),
    el('p', {
      text: '明示的に有効化した接続で最大20投稿を送信します。非公開案件の資料は除外します。費用と正確な入力は予約履歴で確認できます。',
    }),
    button(
      '重要トピックを抽出',
      async () => {
        const id = await api.call('ai.topics.queue', {
          feedId: source.feedId,
          runId: Number(runSelect.value),
        });
        toast(`解析ジョブ #${id} を予約しました`);
        await renderSocialList();
      },
      'secondary',
    ),
  ]);
  for (const job of data.jobs) analysis.append(await jobElement(job));
  detail.append(analysis);
}
async function editSocial(source) {
  const enabled = el('input', { type: 'checkbox', name: 'aiEnabled', checked: source.aiEnabled });
  const result = await modal('SNSの収集・自動抽出', [
    el('p', {
      text: `${source.provider} / ${source.target}（検索条件の変更は別の情報源として登録）`,
    }),
    field('収集間隔（分）', numeric(source.interval, 'interval', 15, 1440)),
    field('対象期間（時間）', numeric(source.windowHours, 'windowHours', 1, 168)),
    field(
      'AIの評価観点（公開情報のみ）',
      el('textarea', { name: 'criteria', text: source.criteria, maxlength: 2000 }),
    ),
    checkedField('定期収集後に自動でAI抽出する（有料の場合があります）', enabled),
  ]);
  if (!result) return;
  await api.call('social.save', {
    ...source,
    interval: Number(result.interval),
    windowHours: Number(result.windowHours),
    criteria: result.criteria,
    aiEnabled: result.aiEnabled === 'on',
  });
  await boot();
  await renderSocialList();
}
async function renderAISettings() {
  const root = $('#ai-settings-root');
  if (!root) return;
  const data = await api.call('ai.state'),
    global = data.global;
  const selectedProvider = state.aiProvider || global.active;
  const provider = el(
    'select',
    { 'aria-label': 'AIプロバイダ' },
    Object.entries(providerNames).map(([key, label]) =>
      option(key, label, selectedProvider === key),
    ),
  );
  provider.addEventListener(
    'change',
    safe(async () => {
      state.aiProvider = provider.value;
      if (provider.value === 'openrouter' || provider.value === 'orcarouter')
        await api.call('ai.global.save', { ...global, active: provider.value });
      await renderAISettings();
    }),
  );
  const entry = data.configs.find((v) => v.config.provider === selectedProvider),
    c = entry.config,
    local = c.provider === 'ollama-local';
  const model = el('input', {
    name: 'model',
    value: c.model,
    maxlength: 200,
    placeholder: local ? '利用者が用意したモデル名' : 'provider/model',
    'aria-label': 'AIモデル',
  });
  const enabled = el('input', { type: 'checkbox', name: 'enabled', checked: c.enabled });
  const form = el('form', { id: 'ai-config-form', class: 'settings-grid' }, [
    field('モデル（自動選択しません）', model),
    field('出力token上限', numeric(c.maxTokens, 'maxTokens', 128, 2048)),
    field(
      '入力上限単価（USD / 100万token）',
      numeric(c.inputRate / 1000000, 'inputRate', 0, 100, '0.000001'),
    ),
    field(
      '出力上限単価（USD / 100万token）',
      numeric(c.outputRate / 1000000, 'outputRate', 0, 100, '0.000001'),
    ),
    field(
      '1回の費用上限（USD）',
      numeric(c.maxCost / 1000000, 'maxCost', 0.000001, 10, '0.000001'),
    ),
  ]);
  if (local)
    form.append(
      field(
        'モデルのSHA-256 digest',
        el('input', {
          name: 'digest',
          value: c.digest,
          minlength: 64,
          maxlength: 64,
          placeholder: 'ollama /api/tags のdigest',
        }),
      ),
    );
  if (c.provider === 'ollama-cloud')
    form.append(
      field(
        '料金の確認日（UTC）',
        el('input', { type: 'date', name: 'rateDate', value: c.rateDate }),
      ),
    );
  form.append(
    checkedField('この接続を有効にする', enabled),
    el('div', { class: 'form-actions' }, [
      el('button', { type: 'submit', class: 'primary', text: 'AI接続を保存' }),
    ]),
  );
  form.addEventListener(
    'submit',
    safe(async (event) => {
      event.preventDefault();
      const fields = Object.fromEntries(new FormData(form));
      await api.call('ai.config.save', {
        ...c,
        model: fields.model.trim(),
        maxTokens: Number(fields.maxTokens),
        inputRate: Math.round(Number(fields.inputRate) * 1000000),
        outputRate: Math.round(Number(fields.outputRate) * 1000000),
        maxCost: Math.round(Number(fields.maxCost) * 1000000),
        digest: fields.digest ?? c.digest,
        rateDate: fields.rateDate ?? c.rateDate,
        enabled: fields.enabled === 'on',
      });
      toast('接続設定を保存しました。保存だけでは生成しません');
      await renderAISettings();
    }),
  );
  const envNames = {
    openrouter: 'OPENROUTER_API_KEY',
    orcarouter: 'ORCAROUTER_API_KEY',
    'ollama-cloud': 'FEEDASTROLABE_OLLAMA_TOKEN_FILE（0600の所有者専用ファイル）',
    'ollama-local': 'Ollamaを127.0.0.1:11434で起動し、クラウドを無効にしてください',
  };
  const budgetForm = el('form', { id: 'ai-budget-form', class: 'settings-grid case-section' }, [
    field(
      '全接続共通の日次予算（USD）',
      numeric(global.dailyMicro / 1000000, 'dailyMicro', 0.000001, 100, '0.000001'),
    ),
    field('全接続共通の日次回数', numeric(global.dailyCalls, 'dailyCalls', 1, 1000)),
    el('div', { class: 'form-actions' }, [
      el('button', { type: 'submit', class: 'secondary', text: '共有予算を保存' }),
    ]),
  ]);
  budgetForm.addEventListener(
    'submit',
    safe(async (event) => {
      event.preventDefault();
      const v = Object.fromEntries(new FormData(budgetForm));
      await api.call('ai.global.save', {
        ...global,
        dailyMicro: Math.round(Number(v.dailyMicro) * 1000000),
        dailyCalls: Number(v.dailyCalls),
      });
      toast('共有予算を保存しました。消費履歴は保持しています');
      await renderAISettings();
    }),
  );
  root.replaceChildren(
    field('プロバイダ', provider),
    el('p', {
      text: `SNS話題抽出の接続先: ${providerNames[global.active]}。Ollama調査補助の設定・実行とは独立しています。`,
    }),
    el('p', {
      class: 'credential-status',
      text: `${entry.credentialReady ? '実行条件: 資格情報の参照可' : '資格情報が未設定'} · ${envNames[c.provider]}`,
    }),
    el('p', {
      text: 'キーを画面やチャットへ入力する必要はありません。起動環境に設定してください。OpenRouter固有のデータ利用・料金条件を他の接続へ転用しません。',
    }),
    form,
    el('p', {
      text: `本日UTC: ${data.today.calls}回予約 / ${usd(data.today.reservedMicro)}。失敗・不明費用の予約は維持し、プロバイダ切替でリセットしません。`,
    }),
    budgetForm,
  );
}
async function jobElement(job) {
  const box = el('details', { class: 'ai-job', 'data-job-id': job.id }, [
    el('summary', {
      text: `#${job.id} · ${jobStates[job.state]} · ${providerNames[job.provider]} · ${date(job.created)}`,
    }),
  ]);
  box.append(
    el('p', {
      text: `${job.config.model} · 予約 ${usd(job.reserved)} · 申告費用 ${usd(job.actual)}`,
    }),
  );
  if (job.error) box.append(el('p', { class: 'danger', text: job.error }));
  const input = el('details', { class: 'ai-input' }, [
    el('summary', { text: '送信入力・出典・ハッシュ' }),
    el('small', { text: `SHA-256: ${job.inputHash}` }),
    el('pre', { text: JSON.stringify(job.input.body, null, 2) }),
  ]);
  for (const ref of job.input.references)
    input.append(el('p', { text: `[${ref.id}] ${ref.title} · ${ref.url} · ${ref.hash}` }));
  box.append(input);
  if (job.state === 'succeeded') {
    const output = job.result.output;
    if (job.kind === 'topics')
      for (const topic of output.topics)
        box.append(
          el('section', { class: 'topic-result' }, [
            el('h3', { text: `${topic.importance} / 100 · ${topic.title}` }),
            el('p', { text: topic.summary }),
            el('p', { text: `理由: ${topic.reason}` }),
            el('p', { text: `未確認点: ${topic.uncertainty}` }),
            el(
              'div',
              { class: 'button-row' },
              topic.articleIds.map((id) =>
                button(
                  `出典 #${id}`,
                  async () => {
                    await chooseFilter({ mode: 'all', feedId: job.feedId });
                    await openArticle(id);
                  },
                  'subtle',
                ),
              ),
            ),
          ]),
        );
    else {
      box.append(el('div', { class: 'assistant-answer', text: output.answer }));
      for (const claim of output.claims)
        box.append(
          el('p', { text: `${claim.text} ${claim.citations.map((id) => `[E${id}]`).join(' ')}` }),
        );
      box.append(el('p', { text: `未確認点: ${output.uncertainty}` }));
    }
    box.append(
      el('details', {}, [
        el('summary', { text: '利用量・系譜' }),
        el('pre', {
          text: JSON.stringify({ usage: job.result.usage, lineage: job.result.lineage }, null, 2),
        }),
      ]),
    );
    const reviews = await api.call('ai.reviews', { id: job.id });
    const latest = reviews[0];
    box.append(
      el('p', {
        text: latest
          ? `人のレビュー版 ${latest.revision}: ${latest.status} · ${latest.text}`
          : '人のレビューはまだありません。生成内容の真偽は未検証です。',
      }),
      button(
        'レビューを保存',
        async () => {
          const status = el('select', { name: 'status' }, [
            option('draft', '下書き', !latest || latest.status === 'draft'),
            option('reviewed', '確認済み', latest?.status === 'reviewed'),
            option('rejected', '不採用', latest?.status === 'rejected'),
          ]);
          const result = await modal('AI出力のレビュー', [
            field('判定', status),
            field(
              '確認・修正メモ（原出力は保持します）',
              el('textarea', { name: 'text', text: latest?.text || '', maxlength: 100000 }),
            ),
          ]);
          if (!result) return;
          await api.call('ai.review.save', {
            jobId: job.id,
            revision: latest?.revision || 0,
            status: result.status,
            text: result.text,
          });
          toast('レビューを新しい版で保存しました');
          if (job.kind === 'topics') await renderSocialList();
          else await openCase(job.caseId);
        },
        'secondary',
      ),
    );
    if (reviews.length)
      box.append(
        el('details', {}, [
          el('summary', { text: `レビュー履歴 ${reviews.length}版` }),
          ...reviews.map((r) => el('p', { text: `版${r.revision} ${r.status} · ${r.text}` })),
        ]),
      );
  }
  return box;
}
async function appendAssistant(workspace, c, evidence) {
  const section = el('section', { class: 'case-section assistant-section' }, [
    el('h3', { text: '出典付き調査補助' }),
    el('p', {
      text: `案件区分: ${c.classification || 'public'}。選択した根拠だけをプレビューし、承認後に送信します。入力や出力の命令からツール・検索・ファイル操作を実行しません。`,
    }),
  ]);
  const provider = el('select', { name: 'provider', 'aria-label': '調査補助の接続先' }, [
    option('ollama-local', providerNames['ollama-local']),
    option('ollama-cloud', providerNames['ollama-cloud']),
  ]);
  const mode = el(
    'select',
    { name: 'mode', 'aria-label': '調査補助の種類' },
    [
      ['summary', '要約'],
      ['translation', '翻訳'],
      ['compare', '比較'],
      ['qa', '質問への回答'],
    ].map(([k, v]) => option(k, v)),
  );
  const question = el('textarea', {
    name: 'question',
    maxlength: 2000,
    'aria-label': '調査補助への指示',
    placeholder: '知りたいこと・翻訳先など（最大2000文字）',
  });
  const form = el('form', { class: 'assistant-form' }, [
    el('div', { class: 'two-column' }, [field('接続先', provider), field('種類', mode)]),
    field('指示・質問', question),
  ]);
  if (!evidence.length)
    form.append(el('p', { text: '根拠不足です。記事から「根拠を保存」して選択してください。' }));
  for (const e of evidence)
    form.append(
      checkedField(
        `[E${e.id}] ${e.title}`,
        el('input', { type: 'checkbox', name: 'evidenceId', value: e.id }),
      ),
    );
  const previewBox = el('div', { class: 'assistant-preview' });
  form.append(el('button', { type: 'submit', class: 'secondary', text: '送信内容をプレビュー' }));
  form.addEventListener(
    'submit',
    safe(async (event) => {
      event.preventDefault();
      const fields = new FormData(form);
      const preview = await api.call('ai.assistant.preview', {
        caseId: c.id,
        provider: fields.get('provider'),
        mode: fields.get('mode'),
        question: fields.get('question'),
        evidenceIds: fields.getAll('evidenceId').map(Number),
      });
      const approve = el('input', {
        type: 'checkbox',
        'aria-label': '送信内容と費用を確認して承認する',
      });
      previewBox.replaceChildren(
        el('h3', {
          text: `送信先: ${providerNames[preview.provider]} · 予約 ${usd(preview.reserved)}`,
        }),
        el('p', {
          text: 'これは正確な生成要求の本文です。30分以内に承認してください。案件・設定・根拠が変わると再プレビューが必要です。',
        }),
        el('pre', { text: JSON.stringify(preview.input.body, null, 2) }),
        el('small', { text: `SHA-256: ${preview.inputHash}` }),
        checkedField('送信内容と費用を確認して承認する', approve),
        button(
          '承認して生成を予約',
          async () => {
            if (!approve.checked) {
              toast('送信内容への承認を選択してください', true);
              return;
            }
            const id = await api.call('ai.assistant.approve', {
              id: preview.id,
              hash: preview.inputHash,
              approved: true,
            });
            toast(`ジョブ #${id} を予約しました`);
            await openCase(c.id);
          },
          'primary',
        ),
      );
    }),
  );
  section.append(
    form,
    previewBox,
    button('生成履歴を再読み込み', () => openCase(c.id), 'subtle'),
  );
  const jobs = await api.call('ai.jobs', { kind: 'assistant', id: c.id });
  for (const job of jobs) section.append(await jobElement(job));
  if (state.caseId === c.id && workspace.isConnected) workspace.append(section);
}
