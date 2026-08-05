# EP-001 — ESTRUTURA OFICIAL DO REPOSITÓRIO H&A CORE

## 1. Objetivo

Estabelecer documentalmente a estrutura física oficial do repositório H&A CORE, registrando sua organização e a responsabilidade institucional de cada diretório.

A estrutura constitui a referência organizacional para a separação entre documentação, código-fonte, testes, recursos, workflows, scripts, ferramentas e dados de execução do projeto.

## 2. Estrutura do repositório

```text
HANDA_CORE/
├── docs/
│   ├── architecture/
│   ├── engineering/
│   ├── governance/
│   ├── audits/
│   ├── knowledge/
│   └── decisions/
├── src/
│   └── handa_core/
├── tests/
├── resources/
│   ├── icons/
│   ├── images/
│   └── themes/
├── workflows/
├── scripts/
├── tools/
└── storage/
    ├── history/
    ├── learning/
    └── runtime/
```

## 3. Responsabilidade de cada diretório

### `docs/`

Reúne exclusivamente a documentação institucional e técnica do H&A CORE, organizada por disciplina documental.

### `docs/architecture/`

Armazena os documentos pertencentes à disciplina de Arquitetura.

### `docs/engineering/`

Armazena os documentos pertencentes à disciplina de Engenharia.

### `docs/governance/`

Armazena os documentos de Governança do projeto.

### `docs/audits/`

Armazena os documentos resultantes de auditorias realizadas no projeto.

### `docs/knowledge/`

Armazena a Base de Conhecimento documental do projeto.

### `docs/decisions/`

Armazena os registros documentais de decisões do projeto.

### `src/`

Concentra exclusivamente o código-fonte do projeto.

### `src/handa_core/`

Armazena exclusivamente o código-fonte pertencente ao H&A CORE.

### `tests/`

Armazena os artefatos de teste do projeto, separados do código-fonte e da documentação.

### `resources/`

Reúne os recursos do projeto, mantendo-os separados da documentação e do código-fonte.

### `resources/icons/`

Armazena os recursos visuais classificados como ícones.

### `resources/images/`

Armazena os recursos visuais classificados como imagens.

### `resources/themes/`

Armazena os recursos visuais classificados como temas.

### `workflows/`

Armazena os artefatos pertencentes aos workflows do projeto.

### `scripts/`

Armazena os scripts do projeto, separados do código-fonte principal.

### `tools/`

Armazena as ferramentas pertencentes ao repositório.

### `storage/`

Concentra os dados de execução do projeto, organizados segundo sua natureza.

### `storage/history/`

Armazena os dados de execução classificados como histórico.

### `storage/learning/`

Armazena os dados de execução classificados como aprendizado.

### `storage/runtime/`

Armazena os dados relacionados à execução corrente do projeto.

## 4. Diretrizes

- Cada disciplina possui diretório próprio.
- A documentação não deve ser misturada ao código.
- Os recursos visuais permanecem separados da documentação e do código-fonte.
- Os dados de execução permanecem em `storage/`.
- O código-fonte permanece exclusivamente em `src/`.

## 5. Resumo Executivo

A estrutura oficial do repositório H&A CORE foi estabelecida como referência organizacional para toda evolução futura do projeto. Sua organização preserva a separação entre disciplinas documentais, código-fonte, testes, recursos, workflows, scripts, ferramentas e dados de execução.

## 6. Declaração de conformidade

Nenhum diretório foi criado, removido ou alterado durante esta atividade. Nenhum código, documentação, configuração ou recurso existente foi modificado. O documento registra exclusivamente a estrutura oficial previamente materializada no repositório H&A CORE. Nenhuma atividade posterior foi iniciada.
