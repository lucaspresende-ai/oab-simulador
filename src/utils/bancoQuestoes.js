import bancoUnificado from '../../assets/banco_unificado.json';

export function obterExamesDisponiveis() {
  const exames = new Set();

  bancoUnificado.forEach((questao) => {
    if (typeof questao.exame === 'number' && !Number.isNaN(questao.exame)) {
      exames.add(questao.exame);
    }
  });

  return [...exames].sort((a, b) => a - b);
}
