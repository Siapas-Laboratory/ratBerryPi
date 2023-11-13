classdef RatBerryClient
    %CLIENT Summary of this class goes here
    %   Detailed explanation goes here
    
    properties
        host
        port
        connected
        conn
    end
    
    methods
        function self = RatBerryClient(host, port)
            self.host = host;
            self.port = port;
            self.connected = false;
        end
        
        function self = connect(self)
            %METHOD1 Summary of this method goes here
            %   Detailed explanation goes here
            self.conn = tcpclient(self.host, self.port);
            self.connected = true;
        end

        function reply = run_command(self, command, varargin)
            assert(self.connected, 'not connected')
            if nargin>2
                assert(numel(varargin)==1, 'too many inputs');
                args = varargin{1};
                assert(strcmp(class(args), 'struct'), "invalid input for argument 'args'");
            end
            args.command = command;
            self.conn.write(jsonencode(args));
            while self.conn.NumBytesAvailable == 0; continue; end
            reply = jsondecode(char(self.conn.read()));
        end
        function reply = get(self, req, varargin)
            self.

        end
    end
end

