import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import { ToastContainer} from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import './App.css';
import Admin from './components/Admin';
import Home from './components/Home';
import Userlogin from './components/Userlogin';
import AdminLogin from './components/AdminLogin';
import MACAddressInput from './components/MACAddressInput';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/Admin" element={<Admin />} />
        <Route path="/AdminLogin" element={<AdminLogin />} />
        <Route path="/Userlogin" element={<Userlogin />} />
        <Route path="/MACAddressInput" element={< MACAddressInput/>}></Route>
      </Routes>
      <ToastContainer />
    </Router>
  );
}

export default App;
