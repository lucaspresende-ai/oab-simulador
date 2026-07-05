import React, { useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useFocusEffect } from '@react-navigation/native';

export default function StatsScreen() {
  const [estatisticas, setEstatisticas] = useState([]);
  const [totalGeral, setTotalGeral] = useState({ respondidas: 0, certas: 0 });

  // useFocusEffect recarrega os dados toda vez que você clica na aba "Estatísticas"
  useFocusEffect(
    React.useCallback(() => {
      const carregarEstatisticas = async () => {
        try {
          const statsStr = await AsyncStorage.getItem('estatisticas_oab');
          if (statsStr) {
            const statsObj = JSON.parse(statsStr);
            
            let tRespondidas = 0;
            let tCertas = 0;
            
            // Transforma o objeto salvo em uma lista para facilitar o visual
            const statsArray = Object.keys(statsObj).map(materia => {
              const { respondidas, certas } = statsObj[materia];
              tRespondidas += respondidas;
              tCertas += certas;
              const aproveitamento = Math.round((certas / respondidas) * 100);
              return { materia, respondidas, certas, aproveitamento };
            });

            // Ordena da matéria que ela tem mais dificuldade para a que tem mais facilidade
            statsArray.sort((a, b) => a.aproveitamento - b.aproveitamento);

            setTotalGeral({ respondidas: tRespondidas, certas: tCertas });
            setEstatisticas(statsArray);
          }
        } catch (error) {
          console.error("Erro ao carregar estatísticas", error);
        }
      };
      carregarEstatisticas();
    }, [])
  );

  const limparHistorico = async () => {
    await AsyncStorage.removeItem('estatisticas_oab');
    await AsyncStorage.removeItem('historico_respondidas');
    setEstatisticas([]);
    setTotalGeral({ respondidas: 0, certas: 0 });
    alert("Progresso zerado com sucesso!");
  };

  const aproveitamentoGeral = totalGeral.respondidas > 0 
    ? Math.round((totalGeral.certas / totalGeral.respondidas) * 100) 
    : 0;

  return (
    <View style={styles.container}>
      <View style={styles.headerDashboard}>
        <Text style={styles.tituloDashboard}>Aproveitamento Geral</Text>
        <Text style={styles.numeroDashboard}>{aproveitamentoGeral}%</Text>
        <Text style={styles.textoDashboard}>
          {totalGeral.certas} acertos em {totalGeral.respondidas} questões
        </Text>
      </View>

      <ScrollView style={styles.listaStats}>
        {estatisticas.length === 0 ? (
          <Text style={styles.textoVazio}>Você ainda não respondeu nenhuma questão. Vá treinar!</Text>
        ) : (
          estatisticas.map((item, index) => {
            // Regra do Flat Design: Vermelho se < 50%, Verde se >= 50%
            const corBarra = item.aproveitamento >= 50 ? '#4CAF50' : '#CC0000';

            return (
              <View key={index} style={styles.cardMateria}>
                <View style={styles.linhaInfo}>
                  <Text style={styles.nomeMateria}>{item.materia}</Text>
                  <Text style={[styles.textoAproveitamento, { color: corBarra }]}>
                    {item.aproveitamento}%
                  </Text>
                </View>
                
                <Text style={styles.textoDetalhe}>
                  Acertou {item.certas} de {item.respondidas}
                </Text>

                <View style={styles.barraFundo}>
                  <View style={[styles.barraPreenchimento, { width: `${item.aproveitamento}%`, backgroundColor: corBarra }]} />
                </View>
              </View>
            );
          })
        )}
        
        {/* Botão de reset escondido lá no final para caso ela queira zerar tudo */}
        {estatisticas.length > 0 && (
          <TouchableOpacity style={styles.btnReset} onPress={limparHistorico}>
            <Text style={styles.btnResetTexto}>Zerar todo o meu progresso</Text>
          </TouchableOpacity>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFF' },
  headerDashboard: { backgroundColor: '#1A237E', padding: 25, alignItems: 'center' },
  tituloDashboard: { color: '#E8EAF6', fontSize: 16, textTransform: 'uppercase', letterSpacing: 1 },
  numeroDashboard: { color: '#FFF', fontSize: 48, fontWeight: 'bold', marginVertical: 5 },
  textoDashboard: { color: '#E8EAF6', fontSize: 14 },
  listaStats: { flex: 1, padding: 16 },
  textoVazio: { textAlign: 'center', color: '#666', fontSize: 16, marginTop: 40 },
  cardMateria: { backgroundColor: '#F9F9F9', padding: 15, borderRadius: 8, marginBottom: 15, borderWidth: 1, borderColor: '#EEE' },
  linhaInfo: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 },
  nomeMateria: { fontSize: 16, fontWeight: 'bold', color: '#333', flex: 1 },
  textoAproveitamento: { fontSize: 18, fontWeight: 'bold' },
  textoDetalhe: { fontSize: 12, color: '#666', marginBottom: 10 },
  barraFundo: { height: 10, backgroundColor: '#E0E0E0', borderRadius: 5, overflow: 'hidden' },
  barraPreenchimento: { height: '100%', borderRadius: 5 },
  btnReset: { marginTop: 20, marginBottom: 40, padding: 15, alignItems: 'center' },
  btnResetTexto: { color: '#CC0000', fontSize: 14, fontWeight: 'bold' }
});