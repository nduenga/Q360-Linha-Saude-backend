# Configurar o questionário clínico

Na Administração, abra **Negócio · Regras** e selecione **Questionário clínico**. Crie uma configuração com a chave `underwriting.clinical_questionnaire`, guarde como rascunho e submeta-a para aprovação. Só a versão publicada passa a ser usada por novos questionários.

O valor da configuração tem esta estrutura:

```json
{
  "version": "2026-11-v2",
  "sections": [
    {
      "key": "health",
      "label": "Dados de saúde",
      "questions": [
        {"key": "smoker", "label": "Fuma?", "type": "YES_NO", "required": true},
        {
          "key": "frequency",
          "label": "Com que frequência?",
          "type": "SELECT",
          "required": true,
          "options": ["Diariamente", "Ocasionalmente"],
          "showIf": {"question": "smoker", "equals": true}
        }
      ]
    }
  ]
}
```

Tipos aceites: `YES_NO`, `TEXT`, `NUMBER`, `DATE`, `SELECT` e `MULTI_SELECT`. Os dois últimos exigem `options`. Cada chave de secção e de pergunta deve ser única. Uma pergunta pode ser condicional através de `showIf`.

O sistema guarda uma cópia da estrutura no momento em que o questionário é iniciado. Assim, editar e publicar uma nova versão não altera perguntas nem regras de validação de questionários que já estavam em preenchimento.
