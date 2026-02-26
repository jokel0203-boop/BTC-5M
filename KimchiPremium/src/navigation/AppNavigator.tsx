import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Text } from 'react-native';
import { HomeScreen } from '../screens/HomeScreen';
import { DetailScreen } from '../screens/DetailScreen';
import { SettingsScreen } from '../screens/SettingsScreen';

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

function TabIcon({ label, focused }: { label: string; focused: boolean }) {
  return (
    <Text style={{ fontSize: 10, color: focused ? '#4A90D9' : '#666666' }}>
      {label}
    </Text>
  );
}

export function AppNavigator() {
  return (
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
              <Text style={{ fontSize: 22 }}>{focused ? '📊' : '📊'}</Text>
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
              <Text style={{ fontSize: 22 }}>{focused ? '⚙️' : '⚙️'}</Text>
            ),
          }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
