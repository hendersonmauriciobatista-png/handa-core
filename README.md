# H&A — Handa Core

**Sistema autônomo de análise de mercado, decisão e execução para mercados de criptoativos.**

H&A é uma plataforma de software desenvolvida para observar condições de mercado, identificar oportunidades, aplicar critérios de decisão e risco e coordenar ciclos operacionais de trading por meio de uma arquitetura modular.

O projeto integra componentes de análise de mercado, radar de oportunidades, decisão, gerenciamento de risco e capital, posições, execução, slots operacionais, aprendizado e interface de monitoramento.

---

## Status do Projeto

**Status operacional:** implantado em infraestrutura dedicada e mantido em operação contínua.

**Status de desenvolvimento:** funcional e em evolução contínua.

**Status do repositório:** Baseline 1.0 consolidada e institucionalizada.

O H&A possui histórico de operação contínua em infraestrutura dedicada, enquanto sua arquitetura, documentação, governança e mecanismos de reprodutibilidade continuam sendo formalizados e aperfeiçoados.

A existência de operação contínua não implica que todos os componentes do sistema estejam concluídos ou que toda funcionalidade presente no repositório esteja habilitada para uso em produção.

---

## Visão Geral

O H&A foi concebido como um sistema modular no qual diferentes responsabilidades do ciclo operacional permanecem separadas.

De forma geral, o fluxo do sistema envolve:

1. observação do mercado;
2. avaliação das condições de liquidez;
3. identificação e refinamento de oportunidades;
4. aplicação de critérios de decisão;
5. avaliação de risco e disponibilidade de capital;
6. gerenciamento de slots operacionais;
7. execução do ciclo autorizado;
8. acompanhamento de posições e resultados;
9. registro de eventos e histórico operacional;
10. utilização de informações produzidas pelo próprio sistema em mecanismos de análise e aprendizado.

A implementação concreta de cada etapa pode evoluir independentemente, preservando a separação de responsabilidades da arquitetura.

---

## Arquitetura

A Baseline 1.0 organiza o núcleo principal do projeto em:

`src/handa_core/`

Entre os domínios e componentes presentes no sistema estão estruturas relacionadas a:

- análise de mercado;
- radar e identificação de oportunidades;
- decisão;
- estratégias;
- risco;
- capital;
- posições;
- execução;
- controle e gerenciamento de slots;
- sensores e sinais;
- estado operacional;
- histórico e armazenamento;
- mecanismos de aprendizado;
- interface desktop;
- integração entre componentes do sistema.

A arquitetura é modular e permanece em evolução.

---

## Ciclo Operacional

O H&A trabalha com ciclos contínuos de observação e decisão.

O sistema pode avaliar condições como liquidez e disponibilidade de oportunidades antes de permitir que uma operação avance pelas etapas seguintes do ciclo.

Slots operacionais permitem representar e acompanhar atividades independentes dentro do sistema.

Estados, decisões e eventos produzidos durante a operação podem ser registrados para observação, auditoria e evolução dos componentes internos.

---

## Interface Operacional

O projeto possui interface de monitoramento capaz de representar informações operacionais do sistema.

Entre as informações observáveis na implementação atual estão:

- saldo;
- resultado operacional;
- estado dos slots;
- estado geral do sistema;
- latências;
- histórico de operações;
- atividade do ciclo;
- condições de liquidez do mercado.

A interface constitui uma camada de observação do H&A e não deve ser interpretada isoladamente como responsável pelas decisões do núcleo operacional.

---

## Execução

O projeto possui diferentes caminhos e componentes de execução desenvolvidos ao longo de sua evolução.

A implantação operacional utilizada pelo projeto possui configuração própria de ambiente.

A reprodução completa dessa implantação a partir de um clone limpo do repositório está sendo formalizada como parte da evolução da documentação e da Baseline 1.0.

Por esse motivo, caminhos de execução encontrados no código não devem ser tratados automaticamente como procedimentos oficiais de implantação sem a correspondente validação operacional.

---

## Testes e Validação

O repositório contém testes e artefatos de validação associados a diferentes componentes e fases de desenvolvimento do H&A.

Eles incluem cenários relacionados, entre outros, a:

- execução;
- mercado;
- providers;
- slots;
- ciclos operacionais;
- integração;
- posições;
- lógica de saída;
- estabilidade.

A presença de um teste no repositório não significa, por si só, que ele faça parte de uma suíte oficial de certificação da Baseline 1.0.

A formalização de uma suíte reproduzível e canônica de validação permanece parte da evolução do projeto.

---

## Segurança

Credenciais, chaves de API, segredos e configurações privadas de ambiente não devem fazer parte da Baseline versionada do H&A.

Esses dados devem permanecer fora do controle de versão e ser fornecidos ao sistema exclusivamente por mecanismos apropriados de configuração segura.

Arquivos ou rotinas relacionados a execução em ambiente real exigem revisão explícita antes de utilização.

Nenhuma credencial real deve ser adicionada ao repositório.

---

## Estrutura do Repositório

A organização consolidada utiliza, entre outros, os seguintes diretórios:

```text
handa-core/
├── src/
│   └── handa_core/       # núcleo principal do sistema
├── tests/                # testes e validações
├── docs/                 # documentação e governança
├── resources/            # recursos utilizados pelo projeto
├── storage/              # estruturas de histórico/aprendizado permitidas
├── scripts/              # ferramentas e rotinas auxiliares
└── README.md