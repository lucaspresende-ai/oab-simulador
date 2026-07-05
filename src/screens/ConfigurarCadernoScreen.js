import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet } from 'react-native';
import bancoUnificado from '../../assets/banco_unificado.json'; 

const disciplinasOAB = [
  "Ética", "Filosofia", "Constitucional", "Direitos Humanos", "Eleitoral", 
  "Internacional", "Financeiro", "Tributário", "Administrativo", "Ambiental", 
  "Civil", "ECA", "Consumidor", "Empresarial", "Processo Civil", 
  "Penal", "Processo Penal", "Previdenciário", "Trabalho", "Processo do Trabalho"
];

export default function ConfigurarCadernoScreen({ navigation, route }) {
  const { modo } = route.params || { modo: 'raide' };
  
  const [examesDisponiveis, setExamesDisponiveis] = useState([]);
  const [examesSelecionados, setExamesSelecionados] = useState([]);
  const [disciplinasSelecionadas, setDisciplinasSelecionadas] = useState([]);

  useEffect(() => {
    try {
      const dadosPlanos = Array.isArray(bancoUnificado[0]) ? bancoUnificado.flat() : bancoUnificado;
      let examesUnicos = [...new Set(dadosPlanos.map(q => q.exame || q.Exame || q.id_exame))].filter(Boolean).sort();
      if (examesUnicos.length === 0) examesUnicos = [42, 43, 44, 45, 46];
      setExamesDisponiveis(examesUnicos);
    } catch (error) {
      setExamesDisponiveis([42, 43, 44, 45, 46]);
    }
  }, []);

  const toggleExame = (exame) => {
    setExamesSelecionados(prev => prev.includes(exame) ? prev.filter(e => e !== exame) : [...prev, exame]);
  };

  const toggleDisciplina = (disciplina) => {
    setDisciplinasSelecionadas(prev => prev.includes(disciplina) ? prev.filter(d => d !== disciplina) : [...prev, disciplina]);
  };

  // Regra do Botão: Precisa ter exame selecionado. Se for disciplina, precisa ter disciplina selecionada.
  const podeIniciar = modo === 'raide' 
    ? examesSelecionados.length > 0 
    : (examesSelecionados.length > 0 && disciplinasSelecionadas.length > 0);

  const iniciarSimulador = () => {
    if (podeIniciar) {
      navigation.navigate('Questao', { 
        exames: examesSelecionados, 
        disciplinas: disciplinasSelecionadas,
        modo 
      });
    }
  };

  return (
    <View style={styles.container}>
      <ScrollView style={styles.lista}>
        
        {/* SEÇÃO 1: EXAMES */}
        <Text style={styles.tituloSecao}>1. Selecione os Exames</Text>
        <View style={styles.grade}>
          {examesDisponiveis.map(exame => {
            const isSelected = examesSelecionados.includes(exame);
            return (
              <TouchableOpacity key={exame} style={[styles.itemLista, isSelected && styles.itemSelecionado]} onPress={() => toggleExame(exame)}>
                <View style={[styles.checkbox, isSelected && styles.checkboxAtivo]} />
                <Text style={styles.itemTexto}>Exame #{exame}</Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* SEÇÃO 2: DISCIPLINAS (Só aparece se o modo for disciplina) */}
        {modo === 'disciplina' && (
          <>
            <Text style={styles.tituloSecao}>2. Selecione as Disciplinas</Text>
            {disciplinasOAB.map(disciplina => {
              const isSelected = disciplinasSelecionadas.includes(disciplina);
              return (
                <TouchableOpacity key={disciplina} style={[styles.itemLista, isSelected && styles.itemSelecionado]} onPress={() => toggleDisciplina(disciplina)}>
                  <View style={[styles.checkbox, isSelected && styles.checkboxAtivo]} />
                  <Text style={styles.itemTexto}>{disciplina}</Text>
                </TouchableOpacity>
              );
            })}
          </>
        )}
      </ScrollView>

      <TouchableOpacity style={[styles.btnIniciar, !podeIniciar && styles.btnDesativado]} onPress={iniciarSimulador} disabled={!podeIniciar}>
        <Text style={styles.btnIniciarText}>Iniciar Simulador</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFF', padding: 16 },
  tituloSecao: { fontSize: 18, fontWeight: 'bold', color: '#1A237E', marginTop: 10, marginBottom: 15 },
  grade: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' },
  lista: { flex: 1 },
  itemLista: { flexDirection: 'row', alignItems: 'center', padding: 12, backgroundColor: '#F5F5F5', marginBottom: 10, borderRadius: 8, width: '48%' },
  itemSelecionado: { backgroundColor: '#E8EAF6', borderColor: '#1A237E', borderWidth: 1 },
  checkbox: { width: 20, height: 20, borderRadius: 4, borderWidth: 2, borderColor: '#1A237E', marginRight: 10 },
  checkboxAtivo: { backgroundColor: '#1A237E' },
  itemTexto: { fontSize: 14, color: '#333' },
  btnIniciar: { backgroundColor: '#CC0000', padding: 18, borderRadius: 8, alignItems: 'center', marginTop: 10 },
  btnDesativado: { backgroundColor: '#ccc' },
  btnIniciarText: { color: '#FFF', fontSize: 18, fontWeight: 'bold' }
});