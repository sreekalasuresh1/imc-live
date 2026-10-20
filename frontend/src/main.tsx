import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

class ErrorBoundary extends React.Component<React.PropsWithChildren, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <main className="fatal"><h1>Something went wrong</h1><p>Please reload the page to reconnect.</p><button onClick={() => location.reload()}>Reload classroom</button></main> : this.props.children; }
}

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><ErrorBoundary><App/></ErrorBoundary></React.StrictMode>);
