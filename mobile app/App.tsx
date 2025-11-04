import React, { useState, useEffect, useRef } from 'react';
import { View, Text, FlatList, TouchableOpacity, Alert, StyleSheet, TextInput, SafeAreaView, Modal, ScrollView } from 'react-native';
import { NetworkInfo } from 'react-native-network-info';
import UdpSocket from 'react-native-udp';
import TcpSocket from 'react-native-tcp-socket';
import Share from 'react-native-share';
import { pick, types } from '@react-native-documents/picker';
import ReceiveSharingIntent from 'react-native-receive-sharing-intent';

// Enhanced interfaces matching tkinter functionality
interface Device {
  name: string;
  ip: string;
  port: number;
  status: 'active' | 'inactive';
  lastSeen: number;
}

interface Message {
  id: string;
  from: string;
  content: string;
  timestamp: number;
  type: 'sent' | 'received';
}

interface ReceivedFile {
  id: string;
  filename: string;
  sender: string;
  fileSize: number;
  timestamp: number;
  path?: string;
  status: 'receiving' | 'completed' | 'failed';
}



type TabType = 'devices' | 'messages' | 'files' | 'received-messages' | 'received-files' | 'clipboard' | 'log' | 'network';
type CommMode = 'peer_to_peer' | 'broadcast';

// File Transfer Popup Component
const FileTransferPopup = ({ visible, filename, sender, fileSize, onAccept, onDecline }: {
  visible: boolean;
  filename: string;
  sender: string;
  fileSize: number;
  onAccept: () => void;
  onDecline: () => void;
}) => (
  <Modal visible={visible} transparent animationType="fade">
    <View style={popup_styles.overlay}>
      <View style={popup_styles.popup}>
        <Text style={popup_styles.title}>📤 Incoming File Transfer</Text>
        <Text style={popup_styles.info}>From: {sender}</Text>
        <Text style={popup_styles.info}>File: {filename}</Text>
        <Text style={popup_styles.info}>Size: {(fileSize / (1024 * 1024)).toFixed(2)} MB</Text>
        <Text style={popup_styles.question}>Do you want to accept this file?</Text>
        <View style={popup_styles.buttons}>
          <TouchableOpacity style={popup_styles.acceptBtn} onPress={onAccept}>
            <Text style={popup_styles.btnText}>✅ Accept</Text>
          </TouchableOpacity>
          <TouchableOpacity style={popup_styles.declineBtn} onPress={onDecline}>
            <Text style={popup_styles.btnText}>❌ Decline</Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  </Modal>
);

const App = () => {
  // Navigation state
  const [activeTab, setActiveTab] = useState<TabType>('devices');
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [commMode, setCommMode] = useState<CommMode>('peer_to_peer');

  // Device discovery state
  const [devices, setDevices] = useState<Device[]>([]);
  const [localIP, setLocalIP] = useState<string>('');
  const [deviceCount, setDeviceCount] = useState<number>(0);
  const [deviceName] = useState(`MobileDevice_${Date.now().toString().slice(-4)}`);

  // Messages state
  const [receivedMessages, setReceivedMessages] = useState<Message[]>([]);
  const [messageInput, setMessageInput] = useState<string>('');
  const [selectedDevice, setSelectedDevice] = useState<string>('');

  // Files state
  const [receivedFiles, setReceivedFiles] = useState<ReceivedFile[]>([]);
  const [selectedFilePath, setSelectedFilePath] = useState<string>('');
  const [selectedFileName, setSelectedFileName] = useState<string>('No file selected');
  const [selectedFileSize, setSelectedFileSize] = useState<number>(0);

  // Clipboard state
  const [clipboardText, setClipboardText] = useState<string>('');

  // File transfer popup state
  const [fileTransferPopup, setFileTransferPopup] = useState<{
    visible: boolean;
    filename: string;
    sender: string;
    fileSize: number;
    onDecision: (accept: boolean) => void;
  }>({
    visible: false,
    filename: '',
    sender: '',
    fileSize: 0,
    onDecision: () => {}
  });

  // Log state
  const [logMessages, setLogMessages] = useState<string[]>([]);

  // Network references
  const serverRef = useRef<any>(null);
  const broadcastSocketRef = useRef<any>(null);
  const scannerSocketRef = useRef<any>(null);

  useEffect(() => {
    return () => {
      stopServices();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle shared content
  useEffect(() => {
    const handleSharedContent = (files: any[]) => {
      // Add null/undefined checks
      if (!files || !Array.isArray(files)) {
        logMessage('❌ No files received or invalid data format');
        return;
      }

      files.forEach((file: any, index: number) => {
        if (!file) {
          logMessage(`❌ File at index ${index} is null or undefined`);
          return;
        }

        logMessage(`📋 Processing shared item: ${JSON.stringify(file)}`);

        // Handle different types of shared content
        if (file.contentUri || file.filePath || file.weblink) {
          // DEBUG MODE - Just log everything, no file reading yet
          const filePath = file.contentUri || file.filePath || file.weblink;
          const fileName = file.fileName || file.weblink || 'Shared content';
          
          // Get actual file size using RNFS.stat() - much more efficient than reading content
          (async () => {
            try {
              const RNFS = require('react-native-fs');
              let actualFileSize = file.fileSize || 0;
              
              // Try to get file size using RNFS.stat() first (most reliable)
              if ((!actualFileSize || actualFileSize === 0) && filePath) {
                try {
                  logMessage(`� Getting file stats for: ${filePath}`);
                  const stat = await RNFS.stat(filePath);
                  if (stat.size > 0) {
                    actualFileSize = stat.size;
                    logMessage(`✅ Got actual file size via RNFS.stat: ${actualFileSize} bytes`);
                  }
                } catch (statError) {
                  logMessage(`⚠️ RNFS.stat failed: ${statError}, trying content read...`);
                  
                  // Fallback: Try to read small portion of file to determine size (for small files only)
                  try {
                    const fileContent = await RNFS.readFile(filePath, 'base64');
                    actualFileSize = Math.floor((fileContent.length * 3) / 4);
                    logMessage(`📊 Calculated size from content: ${actualFileSize} bytes`);
                  } catch (readError) {
                    logMessage(`⚠️ Could not determine file size: ${readError}`);
                    actualFileSize = 0;
                  }
                }
              }
              
              const receivedFile: ReceivedFile = {
                id: Date.now().toString() + index,
                filename: fileName,
                sender: 'Shared from another app',
                fileSize: actualFileSize,
                timestamp: Date.now(),
                path: filePath,
                status: 'completed'
              };
              
              setReceivedFiles(prev => [receivedFile, ...prev]);
              logMessage(`📁 Received shared file: ${receivedFile.filename} (${actualFileSize} bytes) - URI: ${filePath}`);
              
              // Show notification
              Alert.alert(
                'Content Received',
                `Shared content "${receivedFile.filename}" has been received.\nSize: ${actualFileSize > 0 ? (actualFileSize / 1024).toFixed(1) + ' KB' : 'Unknown size'}`,
                [{ text: 'OK' }]
              );
            } catch (error) {
              logMessage(`❌ Error processing shared file: ${error}`);
              // Fallback - add file with 0 size
              const receivedFile: ReceivedFile = {
                id: Date.now().toString() + index,
                filename: fileName,
                sender: 'Shared from another app',
                fileSize: 0,
                timestamp: Date.now(),
                path: filePath,
                status: 'completed'
              };
              
              setReceivedFiles(prev => [receivedFile, ...prev]);
              Alert.alert('Content Received', `Shared content "${fileName}" has been received (size unknown).`, [{ text: 'OK' }]);
            }
          })();
        } else if (file.text || file.subject) {
          // Handle shared text
          const content = file.text || file.subject || 'No content';
          const message: Message = {
            id: Date.now().toString() + index,
            from: 'Shared content',
            content: content,
            timestamp: Date.now(),
            type: 'received'
          };
          
          setReceivedMessages(prev => [message, ...prev]);
          logMessage(`💬 Received shared text: ${content.substring(0, 50)}...`);
          
          // Show notification
          Alert.alert(
            'Text Received',
            `Shared text has been received: ${content.substring(0, 100)}${content.length > 100 ? '...' : ''}`,
            [{ text: 'OK' }]
          );
        } else {
          // Log unknown format for debugging
          logMessage(`⚠️ Unknown shared content format: ${JSON.stringify(file)}`);
          
          // Still try to handle it as generic content
          const genericContent = JSON.stringify(file);
          const message: Message = {
            id: Date.now().toString() + index,
            from: 'Shared content (unknown format)',
            content: genericContent,
            timestamp: Date.now(),
            type: 'received'
          };
          
          setReceivedMessages(prev => [message, ...prev]);
          Alert.alert(
            'Content Received',
            'Received shared content in unknown format. Check messages.',
            [{ text: 'OK' }]
          );
        }
      });
    };

    // Get initial shared content when app starts
    try {
      ReceiveSharingIntent.getReceivedFiles(
        (files: any[]) => {
          logMessage(`📨 Received sharing intent with ${files ? files.length : 0} items`);
          if (files && files.length > 0) {
            handleSharedContent(files);
          } else {
            logMessage('📨 No shared files received on app start');
          }
        }, 
        (error: any) => {
          logMessage(`❌ Error getting shared files: ${error?.message || error}`);
          console.error('Share intent error:', error);
        }
      );

      // Clear the received files to prevent re-processing
      ReceiveSharingIntent.clearReceivedFiles();

      // Set up interval to check for new shared content while app is running
      const checkInterval = setInterval(() => {
        ReceiveSharingIntent.getReceivedFiles(
          (files: any[]) => {
            if (files && files.length > 0) {
              logMessage(`📨 New sharing intent detected while app running: ${files.length} items`);
              handleSharedContent(files);
              ReceiveSharingIntent.clearReceivedFiles();
            }
          }, 
          (error: any) => {
            // Silently handle errors for periodic checks
            console.log('Periodic share check error:', error);
          }
        );
      }, 2000); // Check every 2 seconds

      logMessage('✅ Share intent handler initialized with periodic checking');

      return () => {
        clearInterval(checkInterval);
      };
    } catch (error) {
      logMessage(`❌ Exception in share intent handling: ${error}`);
      console.error('Share intent exception:', error);
    }
  }, []);

  // Utility functions
  const logMessage = (message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogMessages(prev => [...prev, `[${timestamp}] ${message}`]);
  };



  const checkNativeModules = () => {
    const modules = [
      { name: 'Share', module: Share },
      { name: 'NetworkInfo', module: NetworkInfo },
      { name: 'UdpSocket', module: UdpSocket },
      { name: 'TcpSocket', module: TcpSocket }
    ];

    modules.forEach(({ name, module }) => {
      if (module) {
        logMessage(`✅ ${name} module is available`);
      } else {
        logMessage(`❌ ${name} module is NOT available`);
      }
    });

    Alert.alert('Module Check', 'Check the log for native module availability');
  };



  // Service control functions (matching tkinter)
  const startServices = async () => {
    if (isRunning) return;

    try {
      logMessage('🚀 Starting services...');
      const ip = await NetworkInfo.getIPV4Address();
      setLocalIP(ip || '');

      if (ip) {
        await startDiscovery(ip);
        await startServer();
        setIsRunning(true);
        logMessage('✅ All services started successfully');

        // Auto-start device discovery
        setTimeout(() => {
          logMessage('🔍 Auto-starting device discovery...');
        }, 1000);
      }
    } catch (error) {
      logMessage(`❌ Failed to start services: ${error}`);
      Alert.alert('Error', 'Failed to start services');
    }
  };

  const stopServices = () => {
    if (!isRunning) return;

    try {
      logMessage('🛑 Stopping services...');

      if (serverRef.current) {
        serverRef.current.close();
        serverRef.current = null;
      }

      if (broadcastSocketRef.current) {
        broadcastSocketRef.current.close();
        broadcastSocketRef.current = null;
      }

      if (scannerSocketRef.current) {
        scannerSocketRef.current.close();
        scannerSocketRef.current = null;
      }

      setIsRunning(false);
      logMessage('✅ Services stopped');
    } catch (error) {
      logMessage(`❌ Error stopping services: ${error}`);
    }
  };

  const startDiscovery = async (ip: string) => {
    // Create UDP socket for broadcasting
    const broadcastSocket = UdpSocket.createSocket({ type: 'udp4' });
    const scannerSocket = UdpSocket.createSocket({ type: 'udp4' });

    broadcastSocketRef.current = broadcastSocket;
    scannerSocketRef.current = scannerSocket;

    // Start broadcasting our presence
    broadcastSocket.bind(() => {
      broadcastSocket.setBroadcast(true);
      logMessage('📡 Started broadcasting device presence');

      const broadcast = () => {
        try {
          const message = JSON.stringify({
            type: 'device_advertisement',
            device_name: deviceName,
            device_id: deviceName + '_' + Date.now(),
            ip: ip,
            port: 8888,
            timestamp: Date.now()
          });

          const broadcastAddr = ip.split('.').slice(0, 3).join('.') + '.255';
          (broadcastSocket as any).send(message, 0, message.length, 8889, broadcastAddr, (error: any) => {
            if (error) {
              logMessage(`❌ Broadcast error: ${error}`);
            }
          });
        } catch (error) {
          logMessage(`❌ Broadcast message creation error: ${error}`);
        }
      };

      broadcast();
      const broadcastInterval = setInterval(broadcast, 5000);

      (broadcastSocket as any).on('error', (error: any) => {
        logMessage(`❌ UDP Broadcast error: ${error}`);
        clearInterval(broadcastInterval);
      });
    });

    // Listen for other devices
    scannerSocket.bind(8889, () => {
      logMessage('👂 Listening for device advertisements on port 8889');

      (scannerSocket as any).on('message', (msg: any, _rinfo: any) => {
        try {
          const data = JSON.parse(msg.toString());
          if (data.type === 'device_advertisement' && data.ip !== ip) {
            setDevices(prev => {
              const exists = prev.find(d => d.ip === data.ip);
              if (!exists) {
                const newDevice: Device = {
                  name: data.device_name || `Device_${data.ip}`,
                  ip: data.ip,
                  port: data.port || 8888,
                  status: 'active',
                  lastSeen: Date.now()
                };
                logMessage(`🆕 New device discovered: ${newDevice.name} (${newDevice.ip})`);
                Alert.alert('New Device Found!', `${newDevice.name}\nIP: ${newDevice.ip}`, [{ text: 'OK' }]);
                setDeviceCount(prev.length + 1);
                return [...prev, newDevice];
              } else {
                // Update existing device
                return prev.map(d =>
                  d.ip === data.ip
                    ? { ...d, lastSeen: Date.now(), status: 'active' as const }
                    : d
                );
              }
            });
          }
        } catch (error) {
          logMessage(`❌ Error parsing device advertisement: ${error}`);
        }
      });

      (scannerSocket as any).on('error', (error: any) => {
        logMessage(`❌ UDP Scanner error: ${error}`);
      });
    });

    logMessage('📡 Device discovery started');
  };

  const startServer = async () => {
    const server = TcpSocket.createServer((socket) => {
      socket.on('data', (data) => {
        try {
          const message = JSON.parse(data.toString());
          handleIncomingMessage(socket, message);
        } catch (e) {
          logMessage(`Server error: ${e}`);
        }
      });
    });

    serverRef.current = server;
    server.listen({ port: 8888, host: '0.0.0.0' });
    logMessage('🖥️ TCP Server started on port 8888');
  };

  const handleIncomingMessage = (socket: any, message: any) => {
    switch (message.type) {
      case 'data':
        // Handle regular message
        const newMessage: Message = {
          id: `msg_${Date.now()}`,
          from: message.sender,
          content: message.payload,
          timestamp: Date.now(),
          type: 'received'
        };
        setReceivedMessages(prev => [newMessage, ...prev]);
        logMessage(`💬 Message from ${message.sender}: ${message.payload}`);
        Alert.alert('Message Received', `From ${message.sender}: ${message.payload}`);
        socket.write(JSON.stringify({ type: 'ack', status: 'received' }));
        break;

      case 'clipboard_data':
        // Handle clipboard sync
        setClipboardText(message.clipboard_content);
        logMessage(`📋 Clipboard synced from ${message.sender}`);
        Alert.alert('Clipboard Updated', `Content from ${message.sender} copied to clipboard`);
        socket.write(JSON.stringify({ type: 'ack', status: 'received' }));
        break;

      case 'file_transfer_request':
        // Handle file transfer request with popup
        showFileTransferDialog(message.filename, message.sender, message.file_size, (accept) => {
          if (accept) {
            socket.write(JSON.stringify({ status: 'accepted' }));
            logMessage(`✅ Accepted file transfer: ${message.filename}`);
            
            // Create file entry with receiving status
            const receivedFile: ReceivedFile = {
              id: `file_${Date.now()}`,
              filename: message.filename,
              sender: message.sender,
              fileSize: message.file_size,
              timestamp: Date.now(),
              status: 'receiving'
            };
            setReceivedFiles(prev => [receivedFile, ...prev]);
            
            // Start receiving the actual file data using Python's chunked protocol
            receivePythonFileData(socket, message.filename, message.file_size, message.sender, receivedFile.id);
          } else {
            socket.write(JSON.stringify({ status: 'declined', reason: 'User declined' }));
            logMessage(`❌ Declined file transfer: ${message.filename}`);
          }
        });
        break;

      case 'file_data_complete':
        // Handle complete file transfer with actual file data
        logMessage(`📁 Received complete file: ${message.filename} from ${message.sender}`);
        
        (async () => {
          try {
            const RNFS = require('react-native-fs');
            
            // Create Downloads directory if it doesn't exist
            const downloadsPath = `${RNFS.ExternalStorageDirectoryPath}/Download`;
            const filePath = `${downloadsPath}/${message.filename}`;
            
            // Ensure Downloads directory exists
            const dirExists = await RNFS.exists(downloadsPath);
            if (!dirExists) {
              await RNFS.mkdir(downloadsPath);
              logMessage(`📁 Created Downloads directory: ${downloadsPath}`);
            }
            
            // Save the file from base64 data
            await RNFS.writeFile(filePath, message.data, 'base64');
            
            // Verify file was written correctly
            const fileStats = await RNFS.stat(filePath);
            logMessage(`📊 File saved: ${filePath}, size: ${fileStats.size} bytes`);
            
            const receivedFile: ReceivedFile = {
              id: `file_${Date.now()}`,
              filename: message.filename,
              sender: message.sender,
              fileSize: fileStats.size,
              timestamp: Date.now(),
              path: filePath,
              status: 'completed'
            };
            
            setReceivedFiles(prev => [receivedFile, ...prev]);
            
            logMessage(`✅ File saved successfully: ${filePath} (${fileStats.size} bytes)`);
            Alert.alert(
              'File Received!', 
              `Successfully received and saved ${message.filename} from ${message.sender}.\n\nSize: ${(fileStats.size / 1024).toFixed(1)} KB\nSaved to: Downloads folder`,
              [{ text: 'OK' }]
            );
            
            // Send acknowledgment
            socket.write(JSON.stringify({ type: 'file_ack', status: 'saved', path: filePath, size: fileStats.size }));
          } catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            logMessage(`❌ Error saving file: ${errorMessage}`);
            Alert.alert('File Save Error', `Failed to save ${message.filename}: ${errorMessage}`);
            socket.write(JSON.stringify({ type: 'file_ack', status: 'error', error: errorMessage }));
          }
        })();
        break;

      default:
        socket.write(JSON.stringify({ type: 'ack', status: 'received' }));
    }
  };

  const showFileTransferDialog = (filename: string, sender: string, fileSize: number, onDecision: (accept: boolean) => void) => {
    setFileTransferPopup({
      visible: true,
      filename,
      sender,
      fileSize,
      onDecision: (accept) => {
        setFileTransferPopup(prev => ({ ...prev, visible: false }));
        onDecision(accept);
      }
    });
  };

  const receivePythonFileData = (socket: any, filename: string, fileSize: number, sender: string, fileId: string) => {
    let receivedBytes = 0;
    let receivedChunks: Uint8Array[] = [];
    let fileCompleted = false;
    
    logMessage(`📥 Starting to receive file from Python: ${filename} (${(fileSize / (1024 * 1024)).toFixed(2)} MB)`);

    const updateProgress = (bytes: number) => {
      const progress = ((bytes / fileSize) * 100).toFixed(1);
      logMessage(`📥 Receiving ${filename}: ${progress}% (${bytes}/${fileSize} bytes)`);
    };

    let buffer = new Uint8Array(0);
    let expectingSize = true;
    let expectedChunkSize = 0;

    socket.on('data', (data: any) => {
      try {
        // Convert received data to Uint8Array and append to buffer
        const newData = new Uint8Array(data);
        const combinedBuffer = new Uint8Array(buffer.length + newData.length);
        combinedBuffer.set(buffer);
        combinedBuffer.set(newData, buffer.length);
        buffer = combinedBuffer;

        // Process buffer according to Python's exact protocol
        while (buffer.length > 0) {
          if (expectingSize) {
            // Need 4 bytes for size header
            if (buffer.length >= 4) {
              // Read chunk size (big-endian 32-bit unsigned integer - matches Python's struct.pack('!I'))
              const view = new DataView(buffer.buffer, buffer.byteOffset, 4);
              expectedChunkSize = view.getUint32(0, false); // false = big-endian
              
              logMessage(`📦 Expecting chunk of ${expectedChunkSize} bytes`);
              
              if (expectedChunkSize === 0) {
                // End marker received - file transfer complete
                fileCompleted = true;
                logMessage(`✅ File received successfully: ${filename} (${receivedChunks.length} chunks, ${receivedBytes} bytes)`);
                
                // Save the file to downloads
                (async () => {
                  try {
                    const RNFS = require('react-native-fs');
                    const downloadsPath = `${RNFS.ExternalStorageDirectoryPath}/Download`;
                    const filePath = `${downloadsPath}/${filename}`;
                    
                    // Ensure Downloads directory exists
                    const dirExists = await RNFS.exists(downloadsPath);
                    if (!dirExists) {
                      await RNFS.mkdir(downloadsPath);
                    }
                    
                    // Combine all chunks into one buffer
                    const totalSize = receivedChunks.reduce((sum, chunk) => sum + chunk.length, 0);
                    const combinedData = new Uint8Array(totalSize);
                    let offset = 0;
                    for (const chunk of receivedChunks) {
                      combinedData.set(chunk, offset);
                      offset += chunk.length;
                    }
                    
                    // Write file as binary string using RNFS
                    let binaryString = '';
                    for (let i = 0; i < combinedData.length; i++) {
                      binaryString += String.fromCharCode(combinedData[i]);
                    }
                    
                    // Write the file directly as binary
                    await RNFS.writeFile(filePath, binaryString, 'ascii');
                    
                    // Verify file was written
                    const fileStats = await RNFS.stat(filePath);
                    logMessage(`📊 File saved: ${filePath}, size: ${fileStats.size} bytes`);
                    
                    setReceivedFiles(prev => prev.map(file => 
                      file.id === fileId 
                        ? { ...file, status: 'completed' as const, path: filePath, fileSize: fileStats.size }
                        : file
                    ));
                    
                    Alert.alert(
                      'File Received!', 
                      `${filename} has been received successfully!\n\nSize: ${(fileStats.size / 1024).toFixed(1)} KB\nFrom: ${sender}\nSaved to: Downloads folder`,
                      [{ text: 'OK' }]
                    );
                    
                  } catch (error) {
                    logMessage(`❌ Error saving file: ${error}`);
                    setReceivedFiles(prev => prev.map(file => 
                      file.id === fileId 
                        ? { ...file, status: 'failed' as const }
                        : file
                    ));
                  }
                })();
                
                socket.end();
                return;
              }
              
              // Remove size header from buffer
              buffer = buffer.slice(4);
              expectingSize = false;
            } else {
              // Not enough data for size header yet
              break;
            }
          } else {
            // Expecting chunk data
            if (buffer.length >= expectedChunkSize) {
              // We have the complete chunk
              const chunk = buffer.slice(0, expectedChunkSize);
              receivedChunks.push(chunk);
              receivedBytes += chunk.length;
              
              // Remove chunk from buffer
              buffer = buffer.slice(expectedChunkSize);
              expectingSize = true;
              
              // Send acknowledgment (exactly like Python expects: b'\x01')
              const ackBuffer = new Uint8Array([0x01]);
              socket.write(ackBuffer);
              
              // Update progress every MB or for small files
              if (receivedBytes % (1024 * 1024) < chunk.length || chunk.length < 65536) {
                updateProgress(receivedBytes);
              }
              
              logMessage(`✅ Received chunk ${receivedChunks.length}: ${chunk.length} bytes (Total: ${receivedBytes}/${fileSize})`);
            } else {
              // Not enough data for complete chunk yet
              break;
            }
          }
        }
      } catch (error) {
        logMessage(`❌ Error receiving file ${filename}: ${error}`);
        
        setReceivedFiles(prev => prev.map(file => 
          file.id === fileId 
            ? { ...file, status: 'failed' as const }
            : file
        ));
        
        Alert.alert('File Reception Failed', `Failed to receive ${filename}: ${error}`);
        socket.end();
      }
    });

    socket.on('error', (error: any) => {
      logMessage(`❌ Socket error during file reception: ${error}`);
      setReceivedFiles(prev => prev.map(file => 
        file.id === fileId 
          ? { ...file, status: 'failed' as const }
          : file
      ));
    });

    socket.on('close', () => {
      if (!fileCompleted && receivedBytes < fileSize) {
        logMessage(`⚠️ Connection closed before complete file reception: ${receivedBytes}/${fileSize} bytes`);
        setReceivedFiles(prev => prev.map(file => 
          file.id === fileId 
            ? { ...file, status: 'failed' as const }
            : file
        ));
      } else if (fileCompleted) {
        logMessage(`🔗 Connection closed after successful file transfer: ${filename}`);
      }
    });
  };

  // Device discovery functions
  const discoverDevices = () => {
    if (!isRunning) {
      Alert.alert('Services not running', 'Please start services first');
      return;
    }

    logMessage('🔍 Starting device discovery...');
    setDevices([]);
    setDeviceCount(0);

    // In a real implementation, you'd trigger a more comprehensive discovery
    // For now, we rely on the UDP broadcast discovery
    setTimeout(() => {
      logMessage(`📱 Discovery complete. Found ${devices.length} devices`);
    }, 3000);
  };

  const refreshDeviceList = () => {
    const now = Date.now();
    setDevices(prev => prev.map(device => ({
      ...device,
      status: (now - device.lastSeen > 30000) ? 'inactive' as const : 'active' as const
    })));
    logMessage('🔄 Device list refreshed');
  };

  // Communication functions
  const sendMessage = async () => {
    if (!messageInput.trim()) {
      Alert.alert('Error', 'Please enter a message');
      return;
    }

    if (commMode === 'peer_to_peer' && !selectedDevice) {
      Alert.alert('Error', 'Please select a device for peer-to-peer messaging');
      return;
    }

    const targetDevice = devices.find(d => d.ip === selectedDevice);

    try {
      if (commMode === 'broadcast') {
        // Send to all devices
        const activeDevices = devices.filter(d => d.status === 'active');
        if (activeDevices.length === 0) {
          Alert.alert('Error', 'No active devices found for broadcast');
          return;
        }
        for (const device of activeDevices) {
          await sendMessageToDevice(device, messageInput.trim());
        }
        logMessage(`📢 Broadcast message sent to ${activeDevices.length} devices`);
      } else {
        // Send to selected device
        if (!targetDevice) {
          Alert.alert('Error', 'Selected device not found');
          return;
        }
        await sendMessageToDevice(targetDevice, messageInput.trim());
        logMessage(`📤 Message sent to ${targetDevice.name}`);
      }

      setMessageInput('');
      Alert.alert('Success', 'Message sent successfully!');
    } catch (error) {
      logMessage(`❌ Failed to send message: ${error}`);
      Alert.alert('Error', 'Failed to send message');
    }
  };

  const sendMessageToDevice = (device: Device, message: string): Promise<void> => {
    return new Promise((resolve, reject) => {
      const client = TcpSocket.createConnection({
        port: device.port,
        host: device.ip,
      }, () => {
        const msg = JSON.stringify({
          type: 'data',
          payload: message,
          sender: deviceName
        });
        client.write(msg);
      });

      client.on('data', () => {
        client.destroy();
        resolve();
      });

      client.on('error', (error) => {
        client.destroy();
        reject(error);
      });

      setTimeout(() => {
        if (!client.destroyed) {
          client.destroy();
          reject(new Error('Connection timeout'));
        }
      }, 5000);
    });
  };

  // File sharing functions
  const selectFile = async () => {
    try {
      logMessage('📂 Opening file picker...');
      
      const result = await pick({
        type: types.allFiles,
        allowMultiSelection: false,
      });
      
      if (result && result.length > 0) {
        const file = result[0];
        
        logMessage(`🔍 PICKER DATA DEBUG - FULL FILE OBJECT:`);
        logMessage(`📋 ${JSON.stringify(file, null, 2)}`);
        logMessage(`🔍 INDIVIDUAL PROPERTIES:`);
        logMessage(`� uri: ${file.uri || 'null'}`);
        logMessage(`📋 name: ${file.name || 'null'}`);
        logMessage(`📋 size: ${file.size || 'null'}`);
        logMessage(`📋 type: ${file.type || 'null'}`);
        
        setSelectedFilePath(file.uri);
        setSelectedFileName(file.name || 'Unknown file');
        setSelectedFileSize(file.size || 0);
        logMessage(`📎 File selected with reported size: ${file.size || 0} bytes`);
        
        Alert.alert(
          'DEBUG: Picker Data Received', 
          `File: ${file.name}\nReported Size: ${file.size || 0} bytes\nURI: ${file.uri}\n\n📜 Check LOGS for full details!`,
          [{ text: 'OK' }]
        );
      }
    } catch (error: any) {
      if (error.code === 'DOCUMENT_PICKER_CANCELED') {
        logMessage('📂 File selection cancelled by user');
      } else {
        logMessage(`❌ File selection error: ${error.message || error}`);
        Alert.alert('File Selection Error', `${error.message || 'Unknown error occurred'}\n\nIf this persists, try rebuilding the app.`);
      }
    }
  };

  // Select a received file as the current file to share
  const selectReceivedFile = (file: ReceivedFile) => {
    if (file.status !== 'completed') {
      Alert.alert('Error', 'Cannot select incomplete files for sharing');
      return;
    }

    if (!file.path) {
      Alert.alert('Error', 'File path not available');
      return;
    }

    setSelectedFilePath(file.path);
    setSelectedFileName(file.filename);
    setSelectedFileSize(file.fileSize);
    logMessage(`📎 Received file selected for sharing: ${file.filename}`);
    Alert.alert('File Selected', `Received file "${file.filename}" is now ready to share!`);
  };

  const shareFileToOtherApps = async () => {
    if (!selectedFilePath) {
      Alert.alert('No File Selected', 'Please select a file first');
      return;
    }

    try {
      const shareOptions = {
        title: 'Share File',
        message: `Sharing ${selectedFileName}`,
        url: `file://${selectedFilePath}`,
        type: 'application/octet-stream',
      };

      await Share.open(shareOptions);
      logMessage(`� File shared successfully: ${selectedFileName}`);
      Alert.alert('Success', 'File shared to other app!');
    } catch (error: any) {
      if (error.message !== 'User did not share') {
        logMessage(`❌ Share error: ${error.message || error}`);
        Alert.alert('Share Error', error.message || 'Failed to share file');
      }
    }
  };  const sendFile = async () => {
    if (!selectedFilePath || !selectedDevice) {
      Alert.alert('Error', 'Please select a file and target device');
      return;
    }

    const targetDevice = devices.find(d => d.ip === selectedDevice);
    if (!targetDevice) {
      Alert.alert('Error', 'Selected device not found');
      return;
    }

    try {
      logMessage(`📤 Initiating file transfer: ${selectedFileName} to ${targetDevice.name}`);

      // Read file information
      const fileInfo = {
        filename: selectedFileName,
        filepath: selectedFilePath,
        sender: deviceName,
        file_size: selectedFileSize
      };

      // Send file transfer request
      await sendFileTransferRequest(targetDevice, fileInfo);

      Alert.alert('File Transfer Initiated', `Transfer request sent to ${targetDevice.name}.\nWaiting for acceptance...`);
      logMessage(`📤 File transfer request sent for ${selectedFileName}`);

    } catch (error) {
      logMessage(`❌ File transfer failed: ${error}`);
      Alert.alert('Error', `File transfer failed: ${error}`);
    }
  };

  const sendFileTransferRequest = (device: Device, fileInfo: any): Promise<void> => {
    return new Promise((resolve, reject) => {
      const client = TcpSocket.createConnection({
        port: device.port,
        host: device.ip,
      }, () => {
        const msg = JSON.stringify({
          type: 'file_transfer_request',
          filename: fileInfo.filename,
          file_size: fileInfo.file_size,
          sender: fileInfo.sender
        });
        client.write(msg);
      });

      const handleInitialResponse = (data: any) => {
        try {
          const response = JSON.parse(data.toString());

          if (response.status === 'accepted') {
            logMessage(`✅ File transfer accepted by ${device.name}`);
            Alert.alert('Transfer Accepted', `${device.name} accepted the file transfer!`);
            
            // Remove this handler before starting file transfer
            client.removeListener('data', handleInitialResponse);
            
            // Start the actual file transfer
            sendActualFileData(client, fileInfo, device).then(() => {
              resolve();
            }).catch((error) => {
              reject(error);
            });
          } else {
            client.destroy();
            logMessage(`❌ File transfer declined by ${device.name}: ${response.reason || 'No reason given'}`);
            Alert.alert('Transfer Declined', `${device.name} declined the file transfer.\nReason: ${response.reason || 'User declined'}`);
            resolve(); // Still resolve, but transfer was declined
          }
        } catch (error) {
          client.destroy();
          reject(new Error(`Invalid response from target device: ${error}`));
        }
      };
      
      client.on('data', handleInitialResponse);

      client.on('error', (error) => {
        client.destroy();
        reject(error);
      });

      setTimeout(() => {
        if (!client.destroyed) {
          client.destroy();
          reject(new Error('File transfer request timeout'));
        }
      }, 10000); // 10 second timeout
    });
  };

  const sendActualFileData = async (client: any, fileInfo: any, device: Device): Promise<void> => {
    try {
      logMessage(`📤 Starting file transfer: ${fileInfo.filename} (${(fileInfo.file_size / (1024 * 1024)).toFixed(2)} MB)`);
      
      // Import RNFS for file operations
      const RNFS = require('react-native-fs');
      
      let actualFileSize: number = fileInfo.file_size || 0;
      
      // Verify file size using RNFS.stat() first
      try {
        logMessage(`� Verifying file size using stat: ${fileInfo.filepath}`);
        const stat = await RNFS.stat(fileInfo.filepath);
        if (stat.size > 0) {
          actualFileSize = stat.size;
          logMessage(`✅ Confirmed file size: ${actualFileSize} bytes`);
        }
      } catch (statError) {
        logMessage(`⚠️ Cannot stat file: ${statError}, using provided size: ${fileInfo.file_size}`);
      }
      
      // Read file as base64 and convert to binary (most reliable approach)
      let binaryData: Uint8Array;
      
      try {
        logMessage(`📖 Reading file content as base64: ${fileInfo.filepath}`);
        const base64Content = await RNFS.readFile(fileInfo.filepath, 'base64');
        logMessage(`✅ File read as base64: ${base64Content.length} chars`);
        
        // Convert base64 to binary using mathematical operations (linter-friendly)
        const base64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
        const bytes: number[] = [];
        
        // Process 4 characters at a time
        for (let i = 0; i < base64Content.length; i += 4) {
          const char1 = base64.indexOf(base64Content[i] || 'A');
          const char2 = base64.indexOf(base64Content[i + 1] || 'A');
          const char3 = base64.indexOf(base64Content[i + 2] || '');
          const char4 = base64.indexOf(base64Content[i + 3] || '');
          
          // Use mathematical operations instead of bitwise
          const bitmap = (char1 * 262144) + (char2 * 4096) + (char3 >= 0 ? char3 * 64 : 0) + (char4 >= 0 ? char4 : 0);
          
          bytes.push(Math.floor(bitmap / 65536) % 256);
          if (char3 !== -1) bytes.push(Math.floor(bitmap / 256) % 256);
          if (char4 !== -1) bytes.push(bitmap % 256);
        }
        
        binaryData = new Uint8Array(bytes);
        logMessage(`✅ Base64 decoded to binary: ${binaryData.length} bytes`);
        
      } catch (readError) {
        logMessage(`❌ Cannot read file: ${readError}`);
        throw new Error(`Cannot access file: ${readError}`);
      }
      
      // Validate that we actually have content
      if (binaryData.length === 0) {
        throw new Error('File appears to be empty - no content read');
      }
      
      if (actualFileSize === 0) {
        throw new Error('Calculated file size is 0 bytes - file may be empty or unreadable');
      }
      
      // Send chunked binary data matching Python's protocol
      return new Promise<void>((resolve, reject) => {
        logMessage(`📦 Ready to send binary data: ${binaryData.length} bytes`);
        
        const chunkSize = 64 * 1024; // 64KB chunks
        let sentBytes = 0;
        let chunkIndex = 0;

        const sendNextChunk = () => {
          try {
            if (sentBytes >= binaryData.length) {
              // Send end marker (4 bytes of 0)
              const endMarker = new Uint8Array([0, 0, 0, 0]);
              client.write(endMarker);
              
              logMessage(`✅ File transfer complete: ${fileInfo.filename} (${binaryData.length} bytes sent)`);
              Alert.alert('Transfer Complete', `Successfully sent ${fileInfo.filename} to ${device.name}!`);
              resolve();
              return;
            }

            // Get next chunk of binary data
            const remainingBytes = binaryData.length - sentBytes;
            const currentChunkSize = Math.min(chunkSize, remainingBytes);
            const binaryChunk = binaryData.slice(sentBytes, sentBytes + currentChunkSize);

            // Send chunk size (4 bytes, big-endian)
            const sizeBytes = new Uint8Array(4);
            const size = currentChunkSize;
            sizeBytes[0] = Math.floor(size / 16777216) % 256;
            sizeBytes[1] = Math.floor(size / 65536) % 256;    
            sizeBytes[2] = Math.floor(size / 256) % 256;      
            sizeBytes[3] = size % 256;
            
            client.write(sizeBytes);

            // Send binary chunk
            client.write(binaryChunk);

            sentBytes += currentChunkSize;
            chunkIndex++;

            // Show progress
            const progress = (sentBytes / binaryData.length) * 100;
            logMessage(`📤 Sending ${fileInfo.filename}: ${progress.toFixed(1)}% (chunk ${chunkIndex}: ${currentChunkSize} bytes)`);

            // Wait for acknowledgment (1 byte: 0x01)
            const handleAck = (data: any) => {
              const ackBuffer = new Uint8Array(data);
              if (ackBuffer.length >= 1 && ackBuffer[0] === 1) {
                client.removeListener('data', handleAck);
                // Continue with next chunk after small delay
                setTimeout(sendNextChunk, 50);
              } else {
                client.removeListener('data', handleAck);
                reject(new Error(`Invalid acknowledgment: expected 1, got ${ackBuffer[0]}`));
              }
            };

            client.on('data', handleAck);

            // Timeout for this chunk
            setTimeout(() => {
              client.removeListener('data', handleAck);
              reject(new Error(`Timeout waiting for chunk ${chunkIndex} acknowledgment`));
            }, 15000); // Longer timeout for larger chunks

          } catch (error) {
            reject(error);
          }
        };

        // Start sending chunks
        sendNextChunk();

        // Overall timeout (10 minutes for large files)
        setTimeout(() => {
          reject(new Error('File transfer timeout - took too long'));
        }, 600000);
      });

    } catch (error) {
      logMessage(`❌ File transfer failed: ${error}`);
      client.destroy();
      throw error;
    }
  };

  // Clipboard functions
  const sendClipboard = async () => {
    if (!clipboardText.trim() || !selectedDevice) {
      Alert.alert('Error', 'Please enter clipboard content and select a device');
      return;
    }

    const targetDevice = devices.find(d => d.ip === selectedDevice);
    if (!targetDevice) {
      Alert.alert('Error', 'Selected device not found');
      return;
    }

    try {
      await sendClipboardToDevice(targetDevice, clipboardText.trim());
      logMessage(`📋 Clipboard sent to ${targetDevice.name}`);
      Alert.alert('Success', 'Clipboard synced successfully!');
    } catch (error) {
      logMessage(`❌ Clipboard sync failed: ${error}`);
      Alert.alert('Error', 'Clipboard sync failed');
    }
  };

  const sendClipboardToDevice = (device: Device, content: string): Promise<void> => {
    return new Promise((resolve, reject) => {
      const client = TcpSocket.createConnection({
        port: device.port,
        host: device.ip,
      }, () => {
        const msg = JSON.stringify({
          type: 'clipboard_data',
          clipboard_content: content,
          sender: deviceName
        });
        client.write(msg);
      });

      client.on('data', () => {
        client.destroy();
        resolve();
      });

      client.on('error', (error) => {
        client.destroy();
        reject(error);
      });

      setTimeout(() => {
        if (!client.destroyed) {
          client.destroy();
          reject(new Error('Connection timeout'));
        }
      }, 5000);
    });
  };



  // Send received message to another device
  const sendReceivedMessage = async (message: Message) => {
    if (!selectedDevice) {
      Alert.alert('Error', 'Please select a device to send the message to');
      return;
    }

    const targetDevice = devices.find(d => d.ip === selectedDevice);
    if (!targetDevice) {
      Alert.alert('Error', 'Selected device not found');
      return;
    }

    try {
      logMessage(`📤 Forwarding received message to ${targetDevice.name}`);
      await sendMessageToDevice(targetDevice, message.content);
      
      Alert.alert(
        'Message Forwarded', 
        `Message forwarded to ${targetDevice.name}`
      );
      logMessage(`📤 Message forwarded: "${message.content.substring(0, 50)}..." → ${targetDevice.name}`);

    } catch (error) {
      logMessage(`❌ Message forward failed: ${error}`);
      Alert.alert('Error', `Failed to forward message: ${error}`);
    }
  };

  // Clear functions
  const clearReceivedMessages = () => {
    setReceivedMessages([]);
    logMessage('🗑️ Received messages cleared');
  };

  const clearReceivedFiles = () => {
    setReceivedFiles([]);
    logMessage('🗑️ Received files cleared');
  };

  const clearLog = () => {
    setLogMessages([]);
  };

  // UI Render functions
  const renderTabContent = () => {
    switch (activeTab) {
      case 'devices':
        return renderDevicesTab();
      case 'messages':
        return renderMessagesTab();
      case 'files':
        return renderFilesTab();
      case 'received-messages':
        return renderReceivedMessagesTab();
      case 'received-files':
        return renderReceivedFilesTab();
      case 'clipboard':
        return renderClipboardTab();
      case 'log':
        return renderLogTab();
      case 'network':
        return renderNetworkTab();
      default:
        return renderDevicesTab();
    }
  };

  const renderDevicesTab = () => (
    <View style={styles.tabContent}>
      <View style={styles.controlSection}>
        <Text style={styles.sectionTitle}>Service Control</Text>
        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[styles.button, isRunning ? styles.disabledButton : styles.successButton]}
            onPress={startServices}
            disabled={isRunning}
          >
            <Text style={isRunning ? styles.disabledButtonText : styles.buttonText}>
              🚀 Start Services
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.button, !isRunning ? styles.disabledButton : styles.dangerButton]}
            onPress={stopServices}
            disabled={!isRunning}
          >
            <Text style={!isRunning ? styles.disabledButtonText : styles.buttonText}>
              🛑 Stop Services
            </Text>
          </TouchableOpacity>
        </View>
        <Text style={[styles.status, isRunning ? styles.statusRunning : styles.statusStopped]}>
          Status: {isRunning ? 'Running' : 'Stopped'}
        </Text>
      </View>

      <View style={styles.controlSection}>
        <Text style={styles.sectionTitle}>Device Discovery</Text>
        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[styles.button, !isRunning ? styles.disabledButton : styles.infoButton]}
            onPress={discoverDevices}
            disabled={!isRunning}
          >
            <Text style={!isRunning ? styles.disabledButtonText : styles.buttonText}>
              🔍 Discover Devices
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.button, !isRunning ? styles.disabledButton : styles.warningButton]}
            onPress={refreshDeviceList}
            disabled={!isRunning}
          >
            <Text style={!isRunning ? styles.disabledButtonText : styles.buttonText}>
              🔄 Refresh List
            </Text>
          </TouchableOpacity>
        </View>
        <Text style={styles.info}>Devices found: {deviceCount}</Text>
      </View>

      <View style={styles.controlSection}>
        <Text style={styles.sectionTitle}>Communication Mode</Text>
        <View style={styles.radioGroup}>
          <TouchableOpacity
            style={styles.radioOption}
            onPress={() => setCommMode('peer_to_peer')}
          >
            <Text style={styles.radioText}>
              {commMode === 'peer_to_peer' ? '🔘' : '⚪'} 📡 Peer-to-Peer (Direct Send)
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.radioOption}
            onPress={() => setCommMode('broadcast')}
          >
            <Text style={styles.radioText}>
              {commMode === 'broadcast' ? '🔘' : '⚪'} 📢 Broadcast (Send to All)
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.deviceList}>
        <Text style={styles.sectionTitle}>📱 Devices ({devices.length})</Text>
        <FlatList
          data={devices}
          keyExtractor={(item) => item.ip}
          renderItem={({ item }) => (
            <View style={[styles.deviceItem, item.status === 'active' ? styles.activeDevice : styles.inactiveDevice]}>
              <Text style={styles.deviceName}>{item.name}</Text>
              <Text style={styles.deviceIP}>{item.ip}</Text>
              <Text style={styles.deviceStatus}>
                {item.status === 'active' ? '🟢 Active' : '🔴 Inactive'}
              </Text>
              <Text style={styles.deviceTime}>
                {Math.floor((Date.now() - item.lastSeen) / 1000)}s ago
              </Text>
            </View>
          )}
          ListEmptyComponent={
            <Text style={styles.emptyText}>No devices found yet...</Text>
          }
        />
      </View>
    </View>
  );

  const renderMessagesTab = () => (
    <View style={styles.tabContent}>
      <View style={styles.targetSelection}>
        <Text style={styles.sectionTitle}>Target Selection ({commMode === 'peer_to_peer' ? 'Peer-to-Peer' : 'Broadcast'})</Text>
        {commMode === 'peer_to_peer' && (
          <View style={styles.pickerContainer}>
            <Text>Select Target Device:</Text>
            <ScrollView horizontal style={styles.deviceSelector}>
              {devices.filter(d => d.status === 'active').length > 0 ? (
                devices.filter(d => d.status === 'active').map((device) => (
                  <TouchableOpacity
                    key={device.ip}
                    style={[
                      styles.deviceSelectorItem,
                      selectedDevice === device.ip && styles.selectedDevice
                    ]}
                    onPress={() => setSelectedDevice(device.ip)}
                  >
                    <Text style={
                      selectedDevice === device.ip
                        ? styles.selectedDeviceText
                        : styles.deviceSelectorText
                    }>
                      {device.name} ({device.ip})
                    </Text>
                  </TouchableOpacity>
                ))
              ) : (
                <View style={styles.noDevicesContainer}>
                  <Text style={styles.noDevicesText}>
                    {!isRunning ? '⚠️ Start services first' : '📱 No active devices found'}
                  </Text>
                </View>
              )}
            </ScrollView>
          </View>
        )}
      </View>

      <View style={styles.messageSection}>
        <Text style={styles.sectionTitle}>Message</Text>
        <TextInput
          style={styles.messageInput}
          value={messageInput}
          onChangeText={setMessageInput}
          placeholder="Enter message to send..."
          multiline
          numberOfLines={4}
        />
        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[
              styles.button,
              (!messageInput.trim() || (commMode === 'peer_to_peer' && !selectedDevice))
                ? styles.disabledButton
                : styles.successButton
            ]}
            onPress={sendMessage}
            disabled={!messageInput.trim() || (commMode === 'peer_to_peer' && !selectedDevice)}
          >
            <Text style={
              (!messageInput.trim() || (commMode === 'peer_to_peer' && !selectedDevice))
                ? styles.disabledButtonText
                : styles.buttonText
            }>
              📤 Send Message {commMode === 'broadcast' ? '(Broadcast)' : '(P2P)'}
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );

  const renderFilesTab = () => (
    <View style={styles.tabContent}>
      <View style={styles.targetSelection}>
        <Text style={styles.sectionTitle}>Target Device</Text>
        <ScrollView horizontal style={styles.deviceSelector}>
          {devices.filter(d => d.status === 'active').length > 0 ? (
            devices.filter(d => d.status === 'active').map((device) => (
              <TouchableOpacity
                key={device.ip}
                style={[
                  styles.deviceSelectorItem,
                  selectedDevice === device.ip && styles.selectedDevice
                ]}
                onPress={() => setSelectedDevice(device.ip)}
              >
                <Text style={
                  selectedDevice === device.ip
                    ? styles.selectedDeviceText
                    : styles.deviceSelectorText
                }>
                  {device.name} ({device.ip})
                </Text>
              </TouchableOpacity>
            ))
          ) : (
            <View style={styles.noDevicesContainer}>
              <Text style={styles.noDevicesText}>
                {!isRunning ? '⚠️ Start services first' : '📱 No active devices found'}
              </Text>
            </View>
          )}
        </ScrollView>
      </View>

      <View style={styles.fileSection}>
        <Text style={styles.sectionTitle}>File Selection</Text>
        <View style={styles.buttonRow}>
          <TouchableOpacity style={[styles.button, styles.primaryButton]} onPress={selectFile}>
            <Text style={styles.buttonText}>📂 Browse & Select File</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.button, !selectedFilePath ? styles.disabledButton : styles.infoButton]} 
            onPress={shareFileToOtherApps}
            disabled={!selectedFilePath}
          >
            <Text style={!selectedFilePath ? styles.disabledButtonText : styles.buttonText}>
              📤 Share to Apps
            </Text>
          </TouchableOpacity>
        </View>

        {/* Show received files that can be selected */}
        {receivedFiles.filter(f => f.status === 'completed').length > 0 && (
          <View style={styles.receivedFilesSection}>
            <Text style={styles.sectionTitle}>📥 Or Select from Received Files</Text>
            <ScrollView style={styles.receivedFilesList} showsVerticalScrollIndicator={false}>
              {receivedFiles.filter(f => f.status === 'completed').map((file) => (
                <TouchableOpacity
                  key={file.id}
                  style={[
                    styles.receivedFileItem,
                    selectedFilePath === file.path && styles.selectedReceivedFile
                  ]}
                  onPress={() => selectReceivedFile(file)}
                >
                  <View style={styles.receivedFileInfo}>
                    <Text style={styles.receivedFileName}>
                      ✅ {file.filename}
                    </Text>
                    <Text style={styles.receivedFileDetails}>
                      From: {file.sender} • {(file.fileSize / (1024 * 1024)).toFixed(2)} MB
                    </Text>
                    <Text style={styles.receivedFileTime}>
                      {new Date(file.timestamp).toLocaleString()}
                    </Text>
                  </View>
                  {selectedFilePath === file.path && (
                    <Text style={styles.selectedIndicator}>📌 Selected</Text>
                  )}
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>
        )}

        <View style={styles.selectedFileInfo}>
          <Text style={styles.selectedFileLabel}>Selected File:</Text>
          <Text style={styles.selectedFileName}>{selectedFileName}</Text>
          {selectedFileSize > 0 && (
            <Text style={styles.selectedFileSize}>
              Size: {(selectedFileSize / (1024 * 1024)).toFixed(2)} MB
            </Text>
          )}
        </View>

        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[
              styles.button,
              (!selectedFilePath || !selectedDevice) ? styles.disabledButton : styles.successButton
            ]}
            onPress={sendFile}
            disabled={!selectedFilePath || !selectedDevice}
          >
            <Text style={(!selectedFilePath || !selectedDevice) ? styles.disabledButtonText : styles.buttonText}>
              📤 Send Selected File
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );

  const renderReceivedMessagesTab = () => (
    <View style={styles.tabContent}>
      <View style={styles.listHeader}>
        <Text style={styles.sectionTitle}>📥 Received Messages ({receivedMessages.length})</Text>
        <TouchableOpacity
          style={[styles.button, styles.dangerButton, styles.clearButton]}
          onPress={clearReceivedMessages}
        >
          <Text style={styles.buttonText}>🗑️ Clear All</Text>
        </TouchableOpacity>
      </View>

      {receivedMessages.length > 0 && (
        <View style={styles.targetSelection}>
          <Text style={styles.sectionTitle}>📡 Forward to Device</Text>
          <ScrollView horizontal style={styles.deviceSelector}>
            {devices.filter(d => d.status === 'active').length > 0 ? (
              devices.filter(d => d.status === 'active').map((device) => (
                <TouchableOpacity
                  key={device.ip}
                  style={[
                    styles.deviceSelectorItem,
                    selectedDevice === device.ip && styles.selectedDevice
                  ]}
                  onPress={() => setSelectedDevice(device.ip)}
                >
                  <Text style={
                    selectedDevice === device.ip
                      ? styles.selectedDeviceText
                      : styles.deviceSelectorText
                  }>
                    {device.name} ({device.ip})
                  </Text>
                </TouchableOpacity>
              ))
            ) : (
              <View style={styles.noDevicesContainer}>
                <Text style={styles.noDevicesText}>
                  {!isRunning ? '⚠️ Start services first' : '📱 No active devices found'}
                </Text>
              </View>
            )}
          </ScrollView>
        </View>
      )}

      <FlatList
        data={receivedMessages}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={styles.messageItem}>
            <View style={styles.fileItemHeader}>
              <View style={styles.fileItemContent}>
                <Text style={styles.messageTime}>{new Date(item.timestamp).toLocaleString()}</Text>
                <Text style={styles.messageFrom}>From: {item.from}</Text>
              </View>
              <TouchableOpacity
                style={[
                  styles.sendButton,
                  !selectedDevice ? styles.disabledSendButton : styles.activeSendButton
                ]}
                onPress={() => sendReceivedMessage(item)}
                disabled={!selectedDevice}
              >
                <Text style={[
                  styles.sendButtonText,
                  !selectedDevice ? styles.disabledSendButtonText : styles.activeSendButtonText
                ]}>
                  📤 Forward
                </Text>
              </TouchableOpacity>
            </View>
            <Text style={styles.messageContent}>{item.content}</Text>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.emptyText}>No messages received yet...</Text>}
      />
    </View>
  );

  const renderReceivedFilesTab = () => (
    <View style={styles.tabContent}>
      <View style={styles.listHeader}>
        <Text style={styles.sectionTitle}>📥 Received Files ({receivedFiles.length})</Text>
        <TouchableOpacity
          style={[styles.button, styles.dangerButton, styles.clearButton]}
          onPress={clearReceivedFiles}
        >
          <Text style={styles.buttonText}>🗑️ Clear All</Text>
        </TouchableOpacity>
      </View>

      {receivedFiles.filter(f => f.status === 'completed').length > 0 && (
        <View style={styles.infoSection}>
          <Text style={styles.infoItem}>
            💡 Tip: Go to "File Sharing" tab to send these files to other devices
          </Text>
        </View>
      )}

      <FlatList
        data={receivedFiles}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={[
            styles.fileItem,
            item.status === 'completed' ? styles.completedFile : 
            item.status === 'receiving' ? styles.receivingFile :
            item.status === 'failed' ? styles.failedFile : {}
          ]}>
            <Text style={styles.fileName}>
              {item.status === 'completed' ? '✅' : 
               item.status === 'receiving' ? '⏳' : 
               item.status === 'failed' ? '❌' : '📄'} {item.filename}
            </Text>
            <Text style={styles.fileInfo}>From: {item.sender}</Text>
            <Text style={styles.fileInfo}>Size: {(item.fileSize / (1024 * 1024)).toFixed(2)} MB</Text>
            <Text style={styles.fileInfo}>
              Status: {item.status === 'completed' ? 'Completed' : 
                      item.status === 'receiving' ? 'Receiving...' : 
                      item.status === 'failed' ? 'Failed' : 'Unknown'}
            </Text>
            {item.path && (
              <Text style={styles.fileInfo}>Path: {item.path}</Text>
            )}
            <Text style={styles.messageTime}>{new Date(item.timestamp).toLocaleString()}</Text>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.emptyText}>No files received yet...</Text>}
      />
    </View>
  );

  const renderClipboardTab = () => (
    <View style={styles.tabContent}>
      <View style={styles.targetSelection}>
        <Text style={styles.sectionTitle}>Target Device</Text>
        <ScrollView horizontal style={styles.deviceSelector}>
          {devices.filter(d => d.status === 'active').length > 0 ? (
            devices.filter(d => d.status === 'active').map((device) => (
              <TouchableOpacity
                key={device.ip}
                style={[
                  styles.deviceSelectorItem,
                  selectedDevice === device.ip && styles.selectedDevice
                ]}
                onPress={() => setSelectedDevice(device.ip)}
              >
                <Text style={
                  selectedDevice === device.ip
                    ? styles.selectedDeviceText
                    : styles.deviceSelectorText
                }>
                  {device.name} ({device.ip})
                </Text>
              </TouchableOpacity>
            ))
          ) : (
            <View style={styles.noDevicesContainer}>
              <Text style={styles.noDevicesText}>
                {!isRunning ? '⚠️ Start services first' : '📱 No active devices found'}
              </Text>
            </View>
          )}
        </ScrollView>
      </View>

      <View style={styles.clipboardSection}>
        <Text style={styles.sectionTitle}>Current Clipboard Content</Text>
        <TextInput
          style={styles.clipboardInput}
          value={clipboardText}
          onChangeText={setClipboardText}
          placeholder="Clipboard content..."
          multiline
          numberOfLines={6}
        />
        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[
              styles.button,
              (!clipboardText.trim() || !selectedDevice) ? styles.disabledButton : styles.infoButton
            ]}
            onPress={sendClipboard}
            disabled={!clipboardText.trim() || !selectedDevice}
          >
            <Text style={(!clipboardText.trim() || !selectedDevice) ? styles.disabledButtonText : styles.buttonText}>
              📤 Send Clipboard Content
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );

  const renderLogTab = () => (
    <View style={styles.tabContent}>
      <View style={styles.listHeader}>
        <Text style={styles.sectionTitle}>📜 Log ({logMessages.length})</Text>
        <TouchableOpacity
          style={[styles.button, styles.dangerButton, styles.clearButton]}
          onPress={clearLog}
        >
          <Text style={styles.buttonText}>🗑️ Clear All</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={logMessages}
        keyExtractor={(item, index) => index.toString()}
        renderItem={({ item }) => (
          <View style={styles.logItem}>
            <Text style={styles.logText}>{item}</Text>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.emptyText}>No log messages yet...</Text>}
      />
    </View>
  );

  const renderNetworkTab = () => (
    <View style={styles.tabContent}>
      <Text style={styles.sectionTitle}>ℹ️ Network Information</Text>
      <View style={styles.infoSection}>
        <Text style={styles.infoItem}>Local IP: {localIP || 'Not available'}</Text>
        <Text style={styles.infoItem}>TCP Port: 8888</Text>
        <Text style={styles.infoItem}>UDP Broadcast Port: 8889</Text>
        <Text style={styles.infoItem}>Device Name: AndroidDevice</Text>
        <Text style={styles.infoItem}>Status: {isRunning ? 'Running' : 'Stopped'}</Text>
        <Text style={styles.infoItem}>Communication Mode: {commMode === 'peer_to_peer' ? 'Peer-to-Peer' : 'Broadcast'}</Text>
        <Text style={styles.infoItem}>Connected Devices: {devices.filter(d => d.status === 'active').length}</Text>
      </View>

      <View style={styles.controlSection}>
        <Text style={styles.sectionTitle}>🔧 Debug Tools</Text>
        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[styles.button, styles.infoButton]}
            onPress={checkNativeModules}
          >
            <Text style={styles.buttonText}>🔍 Check Native Modules</Text>
          </TouchableOpacity>
        </View>
        <Text style={styles.info}>
          If file picker isn't working, try rebuilding the app with: npx react-native run-android
        </Text>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>Enhanced Network Device Manager</Text>

      {/* Tab Bar */}
      <ScrollView horizontal style={styles.tabBar} showsHorizontalScrollIndicator={false}>
        {[
          { key: 'devices', icon: '📱', label: 'Devices' },
          { key: 'messages', icon: '💬', label: 'Messages' },
          { key: 'files', icon: '📁', label: 'File Sharing' },
          { key: 'received-messages', icon: '📥', label: 'Received Messages' },
          { key: 'received-files', icon: '📥', label: 'Received Files' },
          { key: 'clipboard', icon: '📋', label: 'Clipboard' },
          { key: 'log', icon: '📜', label: 'Log' },
          { key: 'network', icon: 'ℹ️', label: 'Network Info' }
        ].map((tab) => (
          <TouchableOpacity
            key={tab.key}
            style={[styles.tab, activeTab === tab.key && styles.activeTab]}
            onPress={() => setActiveTab(tab.key as TabType)}
          >
            <Text style={styles.tabIcon}>{tab.icon}</Text>
            <Text style={[styles.tabLabel, activeTab === tab.key && styles.activeTabLabel]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Tab Content */}
      {renderTabContent()}

      {/* File Transfer Popup */}
      <FileTransferPopup
        visible={fileTransferPopup.visible}
        filename={fileTransferPopup.filename}
        sender={fileTransferPopup.sender}
        fileSize={fileTransferPopup.fileSize}
        onAccept={() => fileTransferPopup.onDecision(true)}
        onDecline={() => fileTransferPopup.onDecision(false)}
      />
    </SafeAreaView>
  );
};

// Popup styles
const popup_styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  popup: {
    backgroundColor: '#f0f0f0',
    padding: 20,
    borderRadius: 10,
    width: '80%',
    maxWidth: 400,
  },
  title: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 15,
    textAlign: 'center',
    color: '#333',
  },
  info: {
    fontSize: 14,
    marginBottom: 8,
    color: '#666',
  },
  question: {
    fontSize: 14,
    marginVertical: 15,
    textAlign: 'center',
    color: '#333',
  },
  buttons: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  acceptBtn: {
    backgroundColor: '#28a745',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 5,
  },
  declineBtn: {
    backgroundColor: '#dc3545',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 5,
  },
  btnText: {
    color: 'white',
    fontWeight: 'bold',
  },
});

// Main styles
const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  title: {
    fontSize: 18,
    fontWeight: 'bold',
    textAlign: 'center',
    paddingVertical: 15,
    backgroundColor: '#f0f0f0',
    borderBottomWidth: 1,
    borderBottomColor: '#ddd',
  },

  // Tab Bar
  tabBar: {
    backgroundColor: '#f8f9fa',
    borderBottomWidth: 1,
    borderBottomColor: '#dee2e6',
    maxHeight: 80,
  },
  tab: {
    paddingHorizontal: 15,
    paddingVertical: 10,
    alignItems: 'center',
    minWidth: 100,
  },
  activeTab: {
    borderBottomWidth: 2,
    borderBottomColor: '#007bff',
  },
  tabIcon: {
    fontSize: 16,
    marginBottom: 2,
  },
  tabLabel: {
    fontSize: 10,
    color: '#6c757d',
    textAlign: 'center',
  },
  activeTabLabel: {
    color: '#007bff',
    fontWeight: 'bold',
  },

  // Content
  tabContent: {
    flex: 1,
    padding: 15,
  },

  // Control sections
  controlSection: {
    marginBottom: 20,
    padding: 15,
    backgroundColor: '#f8f9fa',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#dee2e6',
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 10,
    color: '#343a40',
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 10,
  },
  button: {
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    marginHorizontal: 4,
    minHeight: 44,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.1,
    shadowRadius: 3.84,
    elevation: 5,
  },
  primaryButton: {
    backgroundColor: '#007bff',
    borderWidth: 1,
    borderColor: '#0056b3',
  },
  secondaryButton: {
    backgroundColor: '#6c757d',
    borderWidth: 1,
    borderColor: '#545b62',
  },
  successButton: {
    backgroundColor: '#28a745',
    borderWidth: 1,
    borderColor: '#1e7e34',
  },
  warningButton: {
    backgroundColor: '#ffc107',
    borderWidth: 1,
    borderColor: '#d39e00',
  },
  dangerButton: {
    backgroundColor: '#dc3545',
    borderWidth: 1,
    borderColor: '#bd2130',
  },
  infoButton: {
    backgroundColor: '#17a2b8',
    borderWidth: 1,
    borderColor: '#117a8b',
  },
  disabledButton: {
    backgroundColor: '#e9ecef',
    borderWidth: 1,
    borderColor: '#dee2e6',
    shadowOpacity: 0,
    elevation: 0,
  },
  buttonText: {
    color: 'white',
    fontWeight: '600',
    fontSize: 14,
    textAlign: 'center',
  },
  disabledButtonText: {
    color: '#6c757d',
    fontWeight: '600',
    fontSize: 14,
    textAlign: 'center',
  },
  status: {
    fontSize: 14,
    fontWeight: 'bold',
  },
  statusRunning: {
    color: 'green',
  },
  statusStopped: {
    color: 'red',
  },
  info: {
    fontSize: 14,
    color: '#6c757d',
  },

  // Radio group
  radioGroup: {
    gap: 10,
  },
  radioOption: {
    padding: 10,
  },
  radioText: {
    fontSize: 14,
    color: '#343a40',
  },

  // Device list
  deviceList: {
    flex: 1,
  },
  deviceItem: {
    padding: 12,
    borderRadius: 8,
    marginBottom: 8,
    borderLeftWidth: 3,
  },
  activeDevice: {
    backgroundColor: '#d4edda',
    borderLeftColor: '#28a745',
  },
  inactiveDevice: {
    backgroundColor: '#f8d7da',
    borderLeftColor: '#dc3545',
  },
  deviceName: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#343a40',
  },
  deviceIP: {
    fontSize: 12,
    color: '#6c757d',
  },
  deviceStatus: {
    fontSize: 12,
    marginTop: 2,
  },
  deviceTime: {
    fontSize: 10,
    color: '#6c757d',
    marginTop: 2,
  },

  // Target selection
  targetSelection: {
    marginBottom: 20,
  },
  pickerContainer: {
    marginTop: 10,
  },
  deviceSelector: {
    maxHeight: 50,
  },
  deviceSelectorItem: {
    backgroundColor: '#e9ecef',
    paddingHorizontal: 15,
    paddingVertical: 10,
    borderRadius: 5,
    marginRight: 10,
  },
  selectedDevice: {
    backgroundColor: '#007bff',
  },
  deviceSelectorText: {
    fontSize: 12,
    color: '#343a40',
  },

  // Message section
  messageSection: {
    flex: 1,
  },
  messageInput: {
    borderWidth: 1,
    borderColor: '#dee2e6',
    borderRadius: 5,
    padding: 10,
    marginBottom: 10,
    minHeight: 80,
    textAlignVertical: 'top',
  },

  // File section
  fileSection: {
    flex: 1,
  },
  dropArea: {
    borderWidth: 2,
    borderColor: '#dee2e6',
    borderStyle: 'dashed',
    borderRadius: 8,
    padding: 20,
    margin: 10,
    alignItems: 'center',
    backgroundColor: '#f8f9fa',
  },
  dropText: {
    fontSize: 14,
    color: '#6c757d',
    marginBottom: 10,
  },
  sharedFileItem: {
    padding: 8,
    backgroundColor: '#fff',
    borderRadius: 4,
    marginBottom: 5,
    width: '100%',
  },
  fileType: {
    fontSize: 10,
    color: '#6c757d',
  },

  // Clipboard section
  clipboardSection: {
    flex: 1,
  },
  clipboardInput: {
    borderWidth: 1,
    borderColor: '#dee2e6',
    borderRadius: 5,
    padding: 10,
    marginBottom: 10,
    minHeight: 120,
    textAlignVertical: 'top',
  },

  // List items
  listHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 15,
  },
  messageItem: {
    padding: 12,
    backgroundColor: '#f8f9fa',
    borderRadius: 8,
    marginBottom: 8,
    borderLeftWidth: 3,
    borderLeftColor: '#007bff',
  },
  messageTime: {
    fontSize: 10,
    color: '#6c757d',
    marginBottom: 4,
  },
  messageFrom: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#343a40',
    marginBottom: 4,
  },
  messageContent: {
    fontSize: 14,
    color: '#343a40',
  },
  fileItem: {
    padding: 12,
    backgroundColor: '#f8f9fa',
    borderRadius: 8,
    marginBottom: 8,
    borderLeftWidth: 3,
    borderLeftColor: '#ffc107',
  },
  fileName: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#343a40',
    marginBottom: 4,
  },
  fileInfo: {
    fontSize: 12,
    color: '#6c757d',
    marginBottom: 2,
  },
  logItem: {
    padding: 8,
    backgroundColor: '#f8f9fa',
    borderRadius: 4,
    marginBottom: 4,
  },
  logText: {
    fontSize: 12,
    fontFamily: 'monospace',
    color: '#343a40',
  },

  // Info section
  infoSection: {
    padding: 15,
    backgroundColor: '#f8f9fa',
    borderRadius: 8,
  },
  infoItem: {
    fontSize: 14,
    color: '#343a40',
    marginBottom: 8,
    paddingVertical: 4,
  },

  // Empty state
  emptyText: {
    textAlign: 'center',
    fontSize: 16,
    color: '#6c757d',
    marginTop: 50,
  },

  // File selection styles
  selectedFileInfo: {
    backgroundColor: '#e3f2fd',
    borderRadius: 8,
    padding: 12,
    marginTop: 10,
    marginBottom: 10,
    borderLeftWidth: 4,
    borderLeftColor: '#2196f3',
  },
  selectedFileLabel: {
    fontSize: 12,
    color: '#1976d2',
    fontWeight: '600',
    marginBottom: 4,
  },
  selectedFileName: {
    fontSize: 14,
    color: '#0d47a1',
    fontWeight: 'bold',
  },

  // Clear button style
  clearButton: {
    flex: 0,
    minWidth: 100,
  },

  // No devices container
  noDevicesContainer: {
    paddingHorizontal: 15,
    paddingVertical: 10,
    backgroundColor: '#f8d7da',
    borderRadius: 5,
    marginRight: 10,
  },
  noDevicesText: {
    fontSize: 12,
    color: '#721c24',
    fontStyle: 'italic',
  },

  // Selected device text
  selectedDeviceText: {
    fontSize: 12,
    color: 'white',
  },

  // File status styles
  completedFile: {
    borderLeftColor: '#28a745', // Green for completed
    backgroundColor: '#d4edda',
  },
  receivingFile: {
    borderLeftColor: '#007bff', // Blue for receiving
    backgroundColor: '#cce5ff',
  },
  failedFile: {
    borderLeftColor: '#dc3545', // Red for failed
    backgroundColor: '#f8d7da',
  },

  // File item header for send button
  fileItemHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  fileItemContent: {
    flex: 1,
  },

  // Send button styles
  sendButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 4,
    minWidth: 60,
  },
  activeSendButton: {
    backgroundColor: '#17a2b8',
    borderWidth: 1,
    borderColor: '#117a8b',
  },
  disabledSendButton: {
    backgroundColor: '#e9ecef',
    borderWidth: 1,
    borderColor: '#dee2e6',
  },
  sendButtonText: {
    fontSize: 12,
    fontWeight: '600',
    textAlign: 'center',
  },
  activeSendButtonText: {
    color: 'white',
  },
  disabledSendButtonText: {
    color: '#6c757d',
  },

  // Received files selection styles
  receivedFilesSection: {
    marginVertical: 15,
    padding: 12,
    backgroundColor: '#f8f9fa',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#dee2e6',
    maxHeight: 200,
  },
  receivedFilesList: {
    maxHeight: 120,
  },
  receivedFileItem: {
    padding: 10,
    marginBottom: 8,
    backgroundColor: '#ffffff',
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#e9ecef',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  selectedReceivedFile: {
    borderColor: '#007bff',
    backgroundColor: '#e3f2fd',
  },
  receivedFileInfo: {
    flex: 1,
  },
  receivedFileName: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#343a40',
    marginBottom: 2,
  },
  receivedFileDetails: {
    fontSize: 12,
    color: '#6c757d',
    marginBottom: 2,
  },
  receivedFileTime: {
    fontSize: 10,
    color: '#6c757d',
  },
  selectedIndicator: {
    fontSize: 12,
    color: '#007bff',
    fontWeight: 'bold',
  },
  selectedFileSize: {
    fontSize: 12,
    color: '#1976d2',
    marginTop: 2,
  },
});

export default App;