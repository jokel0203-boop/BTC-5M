import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Text } from 'react-native';
import { HomeScreen } from '../screens/HomeScreen';
import { DetailScreen } from '../screens/DetailScreen';
import { AlertScreen } from '../screens/AlertScreen';
import { SettingsScreen } from '../screens/SettingsScreen';
import { AlertProvider } from '../hooks/useAlerts';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

const screenOptions = {
  headerStyle: { backgroundColor: '#0A0A0A' },
  headerTintColor: '#FFFFFF',
  headerTitleStyle: { fontWeight: '600' as const },
};

function HomeStack() {
  return (
    <Stack.Navigator screenOptions={screenOptions}>
      <Stack.Screen
        name="HomeMain"
        component={HomeScreen}
        options={{ title: '김치 프리미엄' }}
      />
      <Stack.Screen
        name="Detail"
        component={DetailScreen}
        options={({ route }: any) => ({
          title: `${route.params.coin.symbol} 상세`,
        })}
      />
    </Stack.Navigator>
  );
}

export function AppNavigator() {
  return (
    <AlertProvider>
      <NavigationContainer>
        <Tab.Navigator
          screenOptions={{
            tabBarStyle: {
              backgroundColor: '#0A0A0A',
              borderTopColor: '#2A2A2A',
            },
            tabBarActiveTintColor: '#4A90D9',
            tabBarInactiveTintColor: '#666666',
            headerShown: false,
          }}
        >
          <Tab.Screen
            name="Home"
            component={HomeStack}
            options={{
              tabBarLabel: '김프',
              tabBarIcon: ({ focused }) => (
                <Text style={{ fontSize: 22 }}>📊</Text>
              ),
            }}
          />
          <Tab.Screen
            name="Alert"
            component={AlertScreen}
            options={{
              tabBarLabel: '알람',
              headerShown: true,
              headerTitle: '김프 알람',
              ...screenOptions,
              tabBarIcon: ({ focused }) => (
                <Text style={{ fontSize: 22 }}>🔔</Text>
              ),
            }}
          />
          <Tab.Screen
            name="Settings"
            component={SettingsScreen}
            options={{
              tabBarLabel: '설정',
              headerShown: true,
              headerTitle: '설정',
              ...screenOptions,
              tabBarIcon: ({ focused }) => (
                <Text style={{ fontSize: 22 }}>⚙️</Text>
              ),
            }}
          />
        </Tab.Navigator>
      </NavigationContainer>
    </AlertProvider>
  );
}
