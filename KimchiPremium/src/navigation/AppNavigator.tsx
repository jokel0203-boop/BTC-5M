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
import { SettingsProvider } from '../contexts/SettingsContext';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

const screenOptions = {
  headerStyle: { backgroundColor: '#0D0D0D' },
  headerTintColor: '#FFFFFF',
  headerTitleStyle: { fontWeight: '600' as const, fontSize: 16 },
  headerShadowVisible: false,
};

function HomeStack() {
  return (
    <Stack.Navigator screenOptions={screenOptions}>
      <Stack.Screen
        name="HomeMain"
        component={HomeScreen}
        options={{ title: '김치프리미엄' }}
      />
      <Stack.Screen
        name="Detail"
        component={DetailScreen}
        options={({ route }: any) => ({
          title: route.params.coin.symbol,
        })}
      />
    </Stack.Navigator>
  );
}

export function AppNavigator() {
  return (
    <SettingsProvider>
      <AlertProvider>
        <NavigationContainer>
          <Tab.Navigator
            screenOptions={{
              tabBarStyle: {
                backgroundColor: '#0D0D0D',
                borderTopColor: '#1A1A1A',
                borderTopWidth: 0.5,
              },
              tabBarActiveTintColor: '#FFFFFF',
              tabBarInactiveTintColor: '#555',
              headerShown: false,
            }}
          >
            <Tab.Screen
              name="Home"
              component={HomeStack}
              options={{
                tabBarLabel: '시세',
                tabBarIcon: ({ color }) => (
                  <Text style={{ fontSize: 18, color }}>$</Text>
                ),
              }}
            />
            <Tab.Screen
              name="알림"
              component={AlertScreen}
              options={{
                tabBarLabel: '알림',
                headerShown: true,
                headerTitle: '김프 알람',
                ...screenOptions,
                tabBarIcon: ({ color }) => (
                  <Text style={{ fontSize: 16, color }}>!</Text>
                ),
              }}
            />
            <Tab.Screen
              name="설정"
              component={SettingsScreen}
              options={{
                tabBarLabel: '설정',
                headerShown: true,
                headerTitle: '설정',
                ...screenOptions,
                tabBarIcon: ({ color }) => (
                  <Text style={{ fontSize: 16, color }}>*</Text>
                ),
              }}
            />
          </Tab.Navigator>
        </NavigationContainer>
      </AlertProvider>
    </SettingsProvider>
  );
}
