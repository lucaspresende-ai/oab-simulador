import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

const AZUL_ESCURO = '#1A237E';
const VERMELHO = '#C62828';

export default function HomeScreen({ navigation }) {
  return (
    <View style={styles.container}>
      <TouchableOpacity
        style={[styles.botao, styles.botaoAzul]}
        activeOpacity={0.8}
        onPress={() =>
          navigation.navigate('ConfigurarCaderno', { modo: 'raide' })
        }
      >
        <Text style={styles.textoBotao}>Raide Aleatório (Simulado Global)</Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={[styles.botao, styles.botaoVermelho]}
        activeOpacity={0.8}
        onPress={() =>
          navigation.navigate('ConfigurarCaderno', { modo: 'disciplina' })
        }
      >
        <Text style={styles.textoBotao}>Treinar por Disciplina</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    padding: 24,
    justifyContent: 'center',
    gap: 20,
  },
  botao: {
    width: '100%',
    minHeight: 72,
    paddingVertical: 20,
    paddingHorizontal: 16,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 0,
    shadowOpacity: 0,
  },
  botaoAzul: {
    backgroundColor: AZUL_ESCURO,
  },
  botaoVermelho: {
    backgroundColor: VERMELHO,
  },
  textoBotao: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '600',
    textAlign: 'center',
  },
});
