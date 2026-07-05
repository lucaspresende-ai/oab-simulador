const fs = require('fs');
const path = require('path');

const pastaBruta = path.join(__dirname, 'dados_brutos');
const pastaDestino = path.join(__dirname, 'assets');
const arquivoDestino = path.join(pastaDestino, 'banco_unificado.json');

let bancoUnificado = [];

// Lê todos os arquivos da pasta dados_brutos
const arquivos = fs.readdirSync(pastaBruta);

arquivos.forEach(arquivo => {
  if (arquivo.endsWith('.json')) {
    // Pega só os números do nome do arquivo (ex: "questoes46.json" vira "46")
    const numeroExame = arquivo.replace(/\D/g, '');
    
    const caminhoArquivo = path.join(pastaBruta, arquivo);
    const conteudo = fs.readFileSync(caminhoArquivo, 'utf8');
    
    try {
      let questoes = JSON.parse(conteudo);
      
      // Ajusta caso a IA extratora tenha colocado as questões dentro de um objeto
      if (!Array.isArray(questoes)) {
        if (questoes.questoes) questoes = questoes.questoes;
        else questoes = Object.values(questoes).flat();
      }

      // O "Pulo do Gato": Injeta o número do exame e um ID único em cada questão!
      questoes.forEach((q, index) => {
        q.exame = numeroExame;
        q.id_questao = `oab${numeroExame}_${index + 1}`; 
        bancoUnificado.push(q);
      });
      
      console.log(`✅ Sucesso: ${arquivo} lido. Adicionado Exame ${numeroExame}.`);
    } catch (e) {
      console.log(`❌ Erro ao ler o arquivo ${arquivo}. Verifique se é um JSON válido.`);
    }
  }
});

// Garante que a pasta assets existe e salva o super arquivo final
if (!fs.existsSync(pastaDestino)){
    fs.mkdirSync(pastaDestino);
}
fs.writeFileSync(arquivoDestino, JSON.stringify(bancoUnificado, null, 2));

console.log(`\n🚀 BANCO SALVO! Total: ${bancoUnificado.length} questões combinadas prontas para uso.`);