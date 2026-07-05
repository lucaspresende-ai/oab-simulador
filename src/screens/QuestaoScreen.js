import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import bancoUnificado from '../../assets/banco_unificado.json';

export default function QuestaoScreen({ route, navigation }) {
  const { exames = [], disciplinas = [], modo } = route.params || {};
  
  const [questoesFiltradas, setQuestoesFiltradas] = useState([]);
  const [indiceAtual, setIndiceAtual] = useState(0);
  const [respondido, setRespondido] = useState(false);
  const [alternativaSelecionada, setAlternativaSelecionada] = useState(null);

  useEffect(() => {
    const carregarQuestoes = async () => {
      try {
        // 1. Puxa o histórico de questões já respondidas da memória
        const histStr = await AsyncStorage.getItem('historico_respondidas');
        const historico = histStr ? JSON.parse(histStr) : [];

        let dadosPlanos = [];
        if (Array.isArray(bancoUnificado)) {
          dadosPlanos = Array.isArray(bancoUnificado[0]) ? bancoUnificado.flat() : bancoUnificado;
        } else if (bancoUnificado.questoes) {
          dadosPlanos = bancoUnificado.questoes;
        } else {
          dadosPlanos = Object.values(bancoUnificado).flat();
        }
        
        let filtradas = dadosPlanos.filter(q => {
          const idQuestao = q.id_questao || "";
          // Se a questão já está no histórico, pula ela! (Evita duplicidade)
          if (historico.includes(idQuestao)) return false;

          const exameQuestao = String(q.exame || "").trim();
          const exameValido = exames.some(e => String(e).trim() === exameQuestao);
          const materiaQuestao = String(q.materia || "").toLowerCase();
          const disciplinaValida = modo === 'raide' || disciplinas.some(d => materiaQuestao.includes(String(d).toLowerCase()));

          return exameValido && disciplinaValida;
        });

        filtradas = filtradas.sort(() => Math.random() - 0.5);
        setQuestoesFiltradas(filtradas);
      } catch (error) {
        console.error("Erro ao carregar:", error);
      }
    };
    carregarQuestoes();
  }, []);

  const questaoAtual = questoesFiltradas[indiceAtual];

  const handleResponder = async (alternativa, isCorreta) => {
    if (respondido) return; 
    setAlternativaSelecionada(alternativa);
    setRespondido(true);

    try {
      const materia = questaoAtual.materia || "Geral";
      const idQuestao = questaoAtual.id_questao;

      // 1. Salvar no Histórico (para não repetir)
      const histStr = await AsyncStorage.getItem('historico_respondidas');
      const historico = histStr ? JSON.parse(histStr) : [];
      if (!historico.includes(idQuestao)) {
        historico.push(idQuestao);
        await AsyncStorage.setItem('historico_respondidas', JSON.stringify(historico));
      }

      // 2. Salvar no Boletim de Estatísticas
      const statsStr = await AsyncStorage.getItem('estatisticas_oab');
      const stats = statsStr ? JSON.parse(statsStr) : {};
      
      if (!stats[materia]) {
        stats[materia] = { respondidas: 0, certas: 0 };
      }
      
      stats[materia].respondidas += 1;
      if (isCorreta) {
        stats[materia].certas += 1;
      }

      await AsyncStorage.setItem('estatisticas_oab', JSON.stringify(stats));
    } catch (e) {
      console.error("Erro ao salvar dados", e);
    }
  };

  const proximaQuestao = () => {
    setRespondido(false);
    setAlternativaSelecionada(null);
    setIndiceAtual(prev => prev + 1);
  };

  if (questoesFiltradas.length === 0) {
    return (
      <View style={styles.containerCenter}>
        <Text style={styles.erroTexto}>Nenhuma questão inédita encontrada com esses filtros.</Text>
        <TouchableOpacity style={styles.btnVoltar} onPress={() => navigation.goBack()}>
          <Text style={styles.btnVoltarTexto}>Voltar</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (indiceAtual >= questoesFiltradas.length) {
    return (
      <View style={styles.containerCenter}>
        <Text style={styles.sucessoTexto}>Fim do Caderno!</Text>
        <Text style={styles.subtitulo}>Você completou todas as questões disponíveis para este filtro.</Text>
        <TouchableOpacity style={styles.btnVoltar} onPress={() => navigation.navigate('MainTabs')}>
          <Text style={styles.btnVoltarTexto}>Voltar ao Início</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerMateria}>{questaoAtual.materia || "OAB"}</Text>
        <Text style={styles.headerExame}>Exame Ordem OAB #{questaoAtual.exame}</Text>
      </View>

      <ScrollView style={styles.scroll}>
        <Text style={styles.enunciado}>{questaoAtual.texto_pergunta}</Text>
        
        {(questaoAtual.alternativas || []).map((alt, index) => {
          const letra = ['A', 'B', 'C', 'D'][index];
          const corretaNaBase = questaoAtual.resposta_correta;
          const isCorreta = letra === corretaNaBase || String(alt).startsWith(String(corretaNaBase));
          const isSelecionada = alternativaSelecionada === alt;

          let btnStyle = styles.btnAlternativa;
          let textStyle = styles.textoAlternativa;

          if (respondido) {
            if (isCorreta) {
              btnStyle = [styles.btnAlternativa, styles.btnCorreta];
              textStyle = [styles.textoAlternativa, styles.textoBranco];
            } else if (isSelecionada) {
              btnStyle = [styles.btnAlternativa, styles.btnErrada];
              textStyle = [styles.textoAlternativa, styles.textoBranco];
            }
          }

          return (
            <TouchableOpacity 
              key={index} 
              style={btnStyle} 
              onPress={() => handleResponder(alt, isCorreta)}
              activeOpacity={0.7}
            >
              <Text style={textStyle}>{alt}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {respondido && (
        <View style={styles.footer}>
          <TouchableOpacity style={styles.btnAvancar} onPress={proximaQuestao}>
            <Text style={styles.btnAvancarTexto}>Avançar</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFF' },
  containerCenter: { flex: 1, backgroundColor: '#FFF', justifyContent: 'center', alignItems: 'center', padding: 20 },
  header: { backgroundColor: '#1A237E', padding: 15, alignItems: 'center' },
  headerMateria: { color: '#FFF', fontSize: 18, fontWeight: 'bold', textAlign: 'center' },
  headerExame: { color: '#E8EAF6', fontSize: 14, marginTop: 5 },
  scroll: { flex: 1, padding: 16 },
  enunciado: { fontSize: 17, color: '#333', marginBottom: 25, lineHeight: 26, fontWeight: '500' },
  btnAlternativa: { backgroundColor: '#FFF', borderWidth: 2, borderColor: '#E0E0E0', borderRadius: 8, padding: 15, marginBottom: 15 },
  btnCorreta: { backgroundColor: '#4CAF50', borderColor: '#4CAF50' }, 
  btnErrada: { backgroundColor: '#CC0000', borderColor: '#CC0000' }, 
  textoAlternativa: { fontSize: 15, color: '#333', lineHeight: 22 },
  textoBranco: { color: '#FFF', fontWeight: 'bold' },
  footer: { padding: 16, backgroundColor: '#FFF', borderTopWidth: 1, borderColor: '#EEE' },
  btnAvancar: { backgroundColor: '#1A237E', padding: 18, borderRadius: 8, alignItems: 'center' },
  btnAvancarTexto: { color: '#FFF', fontSize: 18, fontWeight: 'bold' },
  erroTexto: { fontSize: 18, color: '#CC0000', textAlign: 'center', marginBottom: 20 },
  sucessoTexto: { fontSize: 24, color: '#4CAF50', fontWeight: 'bold', marginBottom: 10 },
  subtitulo: { fontSize: 16, color: '#666', textAlign: 'center', marginBottom: 20 },
  btnVoltar: { backgroundColor: '#1A237E', padding: 15, borderRadius: 8, width: '100%', alignItems: 'center' },
  btnVoltarTexto: { color: '#FFF', fontSize: 16, fontWeight: 'bold' }
});