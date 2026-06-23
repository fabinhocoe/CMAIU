# CMAIU – Avaliação de Impacto Urbano
**Prefeitura Municipal de Palhoça – SC**

Aplicativo desktop para preenchimento, armazenamento e gestão do **Formulário Padrão de Avaliação de Impacto Urbano, Social e Viário**.

## Como executar

```bash
pip install -r requirements.txt
python app.py
```

## Estrutura

| Aba do App | Conteúdo |
|---|---|
| 1. Dados do Empreendimento | Seção 1 do formulário (1.1 a 1.14) |
| 2–3. Impactos Urbanísticos e Viários | Seções 2 e 3 (2.1 a 3.6) |
| 3.7–5. Impactos Sociais e Infraestrutura | Seções 3.7 a 5.5 + início seção 6 |
| 6. Compensação e Cálculo | Seção 6.1 + cálculo via CUB |
| Registros | Consulta e busca de todos os registros salvos |
| Tabela CUB | Gerenciamento dos valores CUB de referência |

## Banco de Dados

O arquivo `banco_cmaiu.xlsx` é criado automaticamente na mesma pasta do aplicativo.

- **Aba "Registros"**: todos os formulários preenchidos
- **Aba "CUB"**: tabela de valores CUB por mês/categoria (SINDUSCON-SC)

## Cálculo de Compensação

```
Valor = Área (m²) × CUB (R$/m²) × Percentual (%)
```
