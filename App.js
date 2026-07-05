import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import HomeScreen from './src/screens/HomeScreen';
import StatsScreen from './src/screens/StatsScreen';
import ConfigurarCadernoScreen from './src/screens/ConfigurarCadernoScreen';
import QuestaoScreen from './src/screens/QuestaoScreen';

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

// Nosso menu do rodapé
function TabNavigator() {
  return (
    <Tab.Navigator screenOptions={{ 
      headerStyle: { backgroundColor: '#1A237E' }, 
      headerTintColor: '#FFF', 
      tabBarActiveTintColor: '#1A237E' 
    }}>
      <Tab.Screen name="Início" component={HomeScreen} />
      <Tab.Screen name="Estatísticas" component={StatsScreen} />
    </Tab.Navigator>
  );
}

// O empilhamento de telas (uma por cima da outra)
export default function App() {
  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ 
        headerStyle: { backgroundColor: '#1A237E' }, 
        headerTintColor: '#FFF' 
      }}>
        <Stack.Screen name="MainTabs" component={TabNavigator} options={{ headerShown: false }} />
        <Stack.Screen name="ConfigurarCaderno" component={ConfigurarCadernoScreen} options={{ title: 'Caderno de Questões' }} />
        <Stack.Screen name="Questao" component={QuestaoScreen} options={{ title: 'Simulado' }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}